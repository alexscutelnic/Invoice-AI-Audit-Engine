# 🤖 AI-Powered Invoice Audit Engine

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
[![Azure Functions](https://img.shields.io/badge/Azure-Functions-0062AD.svg)](https://azure.microsoft.com/en-us/products/functions/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An automated financial reconciliation system that uses **Azure AI Document Intelligence** to audit supplier invoices against system exports in real-time.

## 🌟 The Problem
Manual invoice auditing is time-consuming and prone to human error. Large-scale print and logistics operations often deal with discrepancies in VAT, hidden surcharges, or mismatched totals that go unnoticed until the end of the month.

## 🚀 The Solution
This solution creates a "Digital Auditor" that:
1. **Triggers** automatically when a JSON export lands in Azure Blob Storage.
2. **Pairs** the export data with the physical PDF invoice.
3. **Extracts** financial data using AI (OCR + Semantic Understanding).
4. **Reconciles** Subtotal, VAT, and Total values.
5. **Flags** anomalies (> £0.10) and generates a daily master report with deep-links back to the source system.

## 🗺️ System Architecture



```text
[PrintIQ Export] --> (Blob Trigger) 
                        |
                 [Azure Function]
            /           |           \
 [Document Intel] [Key Vault] [Pandas Logic]
      (AI OCR)      (Secrets)   (Reconcile)
                        |
            [Output: Daily Excel Report] --> [Logic App Email]

## 🛠️ Tech Stack
* **Language:** Python 3.x
* **Cloud:** Azure Functions (Serverless)
* **AI:** Azure AI Document Intelligence (Prebuilt-Invoice Model)
* **Storage:** Azure Blob Storage
* **Automation:** Azure Logic Apps (Email Notifications)
* **Processing:** Pandas & OpenPyXL

## 📊 Feature: Paired Financial Reporting
The system generates a side-by-side comparison to allow for "Management by Exception."

| Invoice_Number | Status | JSON_Total | AI_Total | Reason | Link |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 14820C1 | 🔴 Anomaly | £6261.36 | £6371.57 | Diff: £110.21 | [Open in System] |
| 14755C1 | 🟢 OK | £11768.74 | £11768.74 | OK | [Open in System] |

## ⚙️ Deployment & Configuration
To deploy this locally or to your Azure tenant:

1. **Clone & Install**:
   ```bash
   git clone [https://github.com/alexscutelnic/Invoice-AI-Audit-Engine.git](https://github.com/alexscutelnic/Invoice-AI-Audit-Engine.git)
   pip install -r requirements.txt

2. **Environment Variables**: Configure the following in local.settings.json or Azure App Settings:

* **KeyVaultUri:** Your Azure Key Vault endpoint.

* **DocIntelEndpoint:** Your AI Document Intelligence URL.

* **PrintIQStorage:** Connection string for source PDFs.

3. **Run**:
  ```bash
  func start

## 🔒 Security & Privacy
This repository contains the application logic only. **All API keys, connection strings, and sensitive URLs have been scrubbed** and are managed via Azure Key Vault and Environment Variables.
