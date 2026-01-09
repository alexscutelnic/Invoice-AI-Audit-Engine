import azure.functions as func
import logging
import json
import pandas as pd
import io
import os
from datetime import datetime, timezone, timedelta
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from openpyxl.styles import PatternFill

app = func.FunctionApp()

# =================================================================
# 1. REAL-TIME TRIGGER: Processes each invoice as it arrives
# =================================================================


@app.blob_trigger(arg_name="myblob", path="invoiceexports/{name}", connection="PrintIQStorage")
def InvoiceAuditTrigger(myblob: func.InputStream):
    logging.info(f"=== PROCESSING INDIVIDUAL BLOB: {myblob.name} ===")

    try:
        # --- 1. Fetch Secrets & Initialize Clients ---
        key_vault_uri = os.environ.get("KeyVaultUri")
        credential = DefaultAzureCredential()
        secret_client = SecretClient(
            vault_url=key_vault_uri, credential=credential)

        doc_intel_key = secret_client.get_secret("DocIntelApiKey").value
        storage_key = secret_client.get_secret("StorageAccountKey").value

        doc_intel_endpoint = os.environ.get("DocIntelEndpoint", "https://your-ai-service.cognitiveservices.azure.com/")
        doc_intel_client = DocumentIntelligenceClient(
            doc_intel_endpoint, AzureKeyCredential(doc_intel_key))

        storage_account_name = os.environ.get("PrintIQAccountName", "your_storage_account")
        iq_connect_str = f"DefaultEndpointsProtocol=https;AccountName={storage_account_name};AccountKey={storage_key};EndpointSuffix=core.windows.net"
        my_storage_connect_str = os.environ.get("AzureWebJobsStorage")

        iq_blob_service = BlobServiceClient.from_connection_string(
            iq_connect_str)
        my_blob_service = BlobServiceClient.from_connection_string(
            my_storage_connect_str)

        # --- 2. Parse JSON Data ---
        json_data = json.loads(myblob.read().decode("utf-8"))
        is_credit = json_data.get("IsCreditNote", False)
        multiplier = -1.0 if is_credit else 1.0

        invid = str(json_data.get("INVID", ""))
        inv_number = str(json_data.get("INVInvoiceNumber", "N/A"))
        supplier = json_data.get("BillingCusName", "Unknown")

        # Financials from JSON
        json_subtotal = float(json_data.get(
            "INVInvoiceSubTotal", 0.0)) * multiplier
        json_vat = float(json_data.get("INVInvoiceGST", 0.0)) * multiplier
        json_total = float(json_data.get("INVInvoiceTotal", 0.0)) * multiplier

        # Build Hyperlink for Excel
        iq_url = f"https://printiq.cubiquityonline.com/Invoicing/CreateInvoice.aspx?INVID={invid}"
        clickable_link = f'=HYPERLINK("{iq_url}", "Open in PrintIQ")'

        # --- 3. Find PDF & Run AI Extraction ---
        pdf_container = iq_blob_service.get_container_client(
            "supplierinvoices")
        blobs = pdf_container.list_blobs(name_starts_with=f"{invid}/")
        target_pdf = next(
            (b for b in blobs if b.name.lower().endswith(".pdf")), None)

        ai_subtotal, ai_vat, ai_total = 0.0, 0.0, 0.0

        if target_pdf:
            pdf_bytes = pdf_container.get_blob_client(
                target_pdf.name).download_blob().readall()
            poller = doc_intel_client.begin_analyze_document(
                "prebuilt-invoice", body=pdf_bytes, content_type="application/octet-stream")
            result = poller.result()

            if result.documents:
                fields = result.documents[0].fields

                def get_val(f):
                    field = fields.get(f)
                    if not field:
                        return 0.0
                    return float(field.value_currency.amount if hasattr(field, "value_currency") and field.value_currency else field.value_number or 0.0)

                ai_subtotal = get_val("SubTotal")
                ai_vat = get_val("TotalTax")
                ai_total = get_val("InvoiceTotal")

        # --- 4. Reconciliation Logic ---
        tot_diff = abs(abs(ai_total) - abs(json_total))
        status = "Anomaly" if tot_diff > 0.10 else "OK"
        reason = "OK" if status == "OK" else f"Diff: £{tot_diff:.2f}"

        # --- 5. Generate Excel with Paired Columns ---
        df = pd.DataFrame([{
            "Invoice_Number": inv_number,
            "PrintIQ_Link": clickable_link,
            "Status": status,
            "Supplier": supplier,
            "JSON_Subtotal": json_subtotal,
            "AI_Subtotal": ai_subtotal,
            "JSON_VAT": json_vat,
            "AI_VAT": ai_vat,
            "JSON_Total": json_total,
            "AI_Total": ai_total,
            "Reason": reason,
            "INVID": invid,
            "Timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        }])

        # --- 6. Upload Individual Report ---
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="AuditReport")

        timestamp = datetime.now().strftime('%H%M%S')
        report_name = f"{status}_{invid}_{timestamp}.xlsx"
        report_container = my_blob_service.get_container_client(
            "audit-reports")

        try:
            report_container.create_container()
        except:
            pass

        report_container.upload_blob(
            name=report_name, data=excel_buffer.getvalue(), overwrite=True)
        logging.info(f"✅ Report uploaded: {report_name}")

    except Exception as e:
        logging.error(f"❌ Final Processing Error: {e}")

# =================================================================
# 2. TIMER TRIGGER: Daily Consolidation at 11 PM
# =================================================================


@app.timer_trigger(schedule="0 0 23 * * *", arg_name="mytimer", run_on_startup=False)
def DailyConsolidator(mytimer: func.TimerRequest) -> None:
    logging.info("=== STARTING DAILY CONSOLIDATION (11 PM) ===")

    try:
        my_storage_connect_str = os.environ.get("AzureWebJobsStorage")
        blob_service = BlobServiceClient.from_connection_string(
            my_storage_connect_str)

        report_container = blob_service.get_container_client("audit-reports")
        summary_container = blob_service.get_container_client(
            "daily-summaries")

        try:
            summary_container.create_container()
        except:
            pass

        all_dfs = []
        limit_time = datetime.now(timezone.utc) - timedelta(hours=24)

        blobs = report_container.list_blobs()
        for b in blobs:
            if b.last_modified > limit_time and b.name.endswith(".xlsx"):
                blob_data = report_container.get_blob_client(
                    b.name).download_blob().readall()
                all_dfs.append(pd.read_excel(io.BytesIO(blob_data)))

        if not all_dfs:
            logging.info("No reports found for today.")
            return

        master_df = pd.concat(all_dfs, ignore_index=True)

        # === GENERATE HYPERLINKS ===
        base_url = os.environ.get("PrintIQ_Base_Url", "https://printiq.cubiquityonline.com")
        master_df['PrintIQ_Link'] = master_df['INVID'].apply(
            lambda x: f'=HYPERLINK("{base_url}/Invoicing/CreateInvoice.aspx?INVID={x}", "Open in PrintIQ")'
        )

        # Enforce Paired Column Order
        cols = [
            "Invoice_Number", "PrintIQ_Link", "Status", "Supplier",
            "JSON_Subtotal", "AI_Subtotal",
            "JSON_VAT", "AI_VAT",
            "JSON_Total", "AI_Total",
            "Reason", "INVID", "Timestamp"
        ]
        master_df = master_df[cols]

        # Create Styled Excel
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            master_df.to_excel(writer, index=False, sheet_name="DailySummary")

            workbook = writer.book
            worksheet = writer.sheets["DailySummary"]
            red_fill = PatternFill(start_color="FFC7CE",
                                   end_color="FFC7CE", fill_type="solid")

            for i, status in enumerate(master_df['Status'], start=2):
                if status == "Anomaly":
                    for cell in worksheet[i]:
                        cell.fill = red_fill

        summary_name = f"Daily_Master_Audit_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        summary_container.upload_blob(
            name=summary_name, data=excel_buffer.getvalue(), overwrite=True)
        logging.info(
            f"✅ Daily Master Report uploaded with working links: {summary_name}")

    except Exception as e:
        logging.error(f"❌ Consolidator Error: {e}")
