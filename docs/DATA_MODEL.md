# Data model

- `Household`: name, owner, members. Owns all financial records. The current application uses the first household for each user.
- `Account`: household, name, type (`cash`, `bank`, `wallet`), opening balance, description, active flag, timestamps. Balance is calculated, not duplicated.
- `Category`: household, name, income/expense type. Default Persian categories are created with a household.
- `Transaction`: household, income/expense/transfer type, positive integer amount, date, source and/or destination account, category for income/expense, note, creator, timestamps. One transfer moves money between two accounts.
- `Asset`: household, name, type, acquisition cost, estimated value, purchase date, notes, active flag, timestamps. Gold is deliberately separate.
- `GoldPurchase`: household, date, decimal weight in grams, amount paid, optional note. The effective paid price per gram is derived.
- `GoldPrice`: one manually entered current price per gram per household.

All money fields use integer toman. No floating point is used for money. Financial foreign keys use `PROTECT` where deleting a referenced record would damage history.
