# Assumptions & Configuration Notes

This document outlines all domain assumptions, schema mappings, and potential differences when switching from synthetic data to real production data.

## 1. Datasets & Currency
- **Currency:** Indian Rupee (INR, `₹`).
- **Period:** 12 months (November 1, 2025 to October 31, 2026).
- **Entities:** 400 merchants, ~60,000 transaction attempts.

## 2. Category List (11 Categories)
1. E-commerce
2. Education
3. Food & Delivery
4. Travel
5. SaaS
6. Fintech
7. Healthcare
8. Gaming
9. Utilities & Bills
10. Nonprofit
11. Retail & D2C

## 3. Payment Methods & Networks
- **Methods:** UPI, Card, Netbanking, EMI, Wallet, BNPL.
- **Card Networks:** Visa, Mastercard, RuPay, Amex (null for non-Card transactions).

## 4. Data Quality & Cleaning Assumptions
- **Duplicate `txn_id`s:** Webhook retries produce duplicate `txn_id` rows; the cleaning pipeline retains the first instance and drops subsequent webhook duplicate retries.
- **Invalid Amounts:** Amounts ≤ 0 or > ₹500,000 are flagged and filtered out during cleaning.
- **Date Formats:** Handles mixed date string encodings (`YYYY-MM-DD HH:MM:SS` and `DD-MM-YYYY HH:MM:SS`).

## 5. Privacy & Suppression Thresholds
- **Minimum Group Size (`min_group_size`):** 10. Any categorical breakdown group with fewer than 10 transactions is suppressed or filtered to prevent re-identification.
- **Identifiers:** All row-level identifiers (`merchant_id`, `txn_id`, `business_name`) are stripped from exported aggregates.
