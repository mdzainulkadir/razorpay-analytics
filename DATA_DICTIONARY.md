# Hypothetical Razorpay-style payments dataset (FICTIONAL)

Period: 2025-11-01 to 2026-10-31. Currency: INR. Seed: 42.

## merchants.csv (400 rows, 1 row per merchant)
| column | type | notes |
|---|---|---|
| merchant_id | string, PK | MID_00001 … MID_00400 |
| business_name | string | fictional, unique |
| category | categorical (11) | E-commerce, Education, Food & Delivery, Travel, SaaS, Fintech, Healthcare, Gaming, Utilities & Bills, Nonprofit, Retail & D2C |
| city | categorical, ~3% null | 14 Indian cities |
| state | categorical | derived from city |
| tier | categorical | Starter (~62%), Growth (~31%), Enterprise (~7%) |
| onboarding_date | date | 2019-06 to 2025-09 |
| kyc_status | categorical | Verified ~90%, Pending ~7%, Rejected ~3% |
| risk_rating | categorical | Low ~70%, Medium ~22%, High ~8% |
| is_international_enabled | bool | more likely for higher tiers |

## transactions.csv (~60,180 rows, 1 row per payment attempt)
| column | type | notes |
|---|---|---|
| txn_id | string | pay_XXXXXXXX; ~180 duplicate rows (webhook retries) |
| merchant_id | string, FK -> merchants | heavy-tailed volume, Enterprise dominates |
| created_at | datetime string | trend growth, weekend + evening peaks, Oct festive uplift |
| amount_inr | float | lognormal by category, 10 to ~190,000 |
| payment_method | categorical | UPI ~54%, Card ~28%, Netbanking ~8%, EMI, Wallet, BNPL |
| card_network | categorical, ~72% null | only for Card: Visa, Mastercard, RuPay, Amex |
| issuing_bank | categorical, ~5% null | null for Wallet/BNPL |
| status | categorical | captured ~89%, failed ~7.5%, refunded ~2.5%, partially_refunded ~1% |
| failure_reason | categorical, null unless failed | 8 reasons |
| refund_amount_inr | float | 0 unless refunded |
| is_international | bool | card only, enabled merchants |
| mdr_rate | float | fee rate by method/network/tier |
| fee_inr | float | amount * mdr_rate on successful txns, else 0 |
| gst_on_fee_inr | float | 18% of fee |
| device_type | categorical | Android, iOS, Desktop Web, Mobile Web |
| customer_city | categorical, ~4% null | |
| api_latency_ms | float | lognormal, 150 to 15,000 |
| retry_count | int | >0 only for failed |

## Planted patterns (good for analysis and dashboard storytelling)
- Failure-rate incident on 2026-03-14, 14:00 to 20:00 (bank server down spike, latency 2x)
- Yes Bank and PNB fail more; Netbanking has the highest failure rate
- Refund rates higher for E-commerce, Retail & D2C, Travel
- Festive uplift in October 2026 and early November 2025
- Duplicate txn_ids (data quality issue to handle)
