# Data model

- `Household`: name, owner, members. Owns all financial records. The current application uses the first household for each user.
- `Account`: household, name, type (`cash`, `bank`, `wallet`), opening balance, description, active flag, timestamps. Balance is calculated, not duplicated.
- `Category`: household, name, income/expense type. Default Persian categories are created with a household.
- `Transaction`: household, income/expense/transfer/debt principal type, positive integer amount, date, source and/or destination account, category for income/expense, note, creator, timestamps. One transfer moves money between two accounts.
- `Obligation`: household, kind (`expected_payment`, `bill`, `debt_owed`, `debt_receivable`), person or organization, positive integer amount, settled amount, due date, optional destination account/category as appropriate, notes, status, creator, timestamps. Status is pending, partial, or settled; overdue is derived from the Tehran-local date and remaining amount.
- `ObligationSettlement`: obligation, one immutable cash transaction, a unique idempotency key, timestamp. The linked transaction holds the actual amount, date, account, and creator. Repeating a request with the same key does not post a second transaction.
- `Loan`: borrowed or lent principal, other party, start/maturity dates, optional annual interest rate, fixed total interest, principal and interest repaid so far, optional origination account and transaction, notes, creator, household. The remaining principal and interest are calculated from the stored totals.
- `LoanInstallment`: monthly Jalali due date and planned total payment for a loan. Installments are optional and are generated as equal amounts at creation.
- `LoanRepayment`: loan, account, actual date, principal and interest portions, linked immutable cash transactions, unique idempotency key, timestamp.
- `AlertPreference`: per-user choices for bill, installment, overdue expected income, and high spending alerts, plus a 0–90 day lead time.
- `Notification`: user and household scoped alert history, unique rule/event key, message, due date, creation and read timestamps.
- `Asset`: household, name, type, acquisition cost, estimated value, purchase date, notes, active flag, timestamps. Gold is deliberately separate.
- `GoldPurchase`: household, user-entered name, purchase date, original and remaining decimal weight in grams, amount paid, optional note. The paid price per gram and remaining cost basis are derived.
- `GoldSale`: household, holding, deposit account, sale date, sold decimal weight, sale price per gram, and derived proceeds. A sale cannot exceed the holding's remaining weight.
- `GoldPrice`: one Navasan 18 karat price per gram and source timestamp per household, refreshed by the Compose updater.

All money fields use integer toman. No floating point is used for money. Financial foreign keys use `PROTECT` where deleting a referenced record would damage history.
