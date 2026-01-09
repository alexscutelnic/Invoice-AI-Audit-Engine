# 🤖 AI-Powered Invoice Audit Engine

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

## 🔒 Security & Privacy
This repository contains the application logic only. **All API keys, connection strings, and sensitive URLs have been scrubbed** and are managed via Azure Key Vault and Environment Variables.