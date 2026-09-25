# Finance rules

All stored monetary values are integer toman. A transaction amount must be positive. Opening balances represent money already held before tracking begins and do not count as income. Negative opening balances and transactions that would overdraw a source account are rejected by the API.

Account balance = opening balance + sum of incoming income and transfers − sum of outgoing expenses and transfers. A transfer is one record with source and destination; its effect on total account balance is zero. Monthly income and expense totals include only their respective transaction types, based on the transaction date in the configured Tehran time zone. Monthly net cash flow = income − expense.

Generic assets use the current manually estimated value. Gold value = total purchased grams × manually entered current price per gram, rounded down to an integer toman. Gold invested = sum of purchase amounts; unrealized profit/loss = current value − invested. A gold purchase currently records the asset only. It does **not** remove cash from an account automatically. If the family paid from a tracked account, they must represent that cash movement separately; proper asset conversion is a later feature and should avoid treating the purchase as ordinary consumption.

Net worth = sum of all account balances, including inactive accounts with remaining money, + active generic asset values + current gold value. No liabilities are tracked in Phase 1. Entering the same initial cash in an account and as an asset will double-count it; accounts should represent liquid money and assets should represent other wealth.
