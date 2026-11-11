# Assumptions

A person who signs in with GitHub and Google under different email addresses gets two separate portfolios. AuthKit links methods only when they share a verified email; this linking was not tested because no test accounts share an email.

## Calculations

- All values are in USD.
- No fees or commissions.
- Dividends are not tracked.
- Cost basis is per lot. Combined positions use weighted average cost across lots and accounts.
- Gains are unrealized only.
- Positions without a current price are excluded from value and gain totals (but still counted in total invested) and listed as missing.

## Market hours

- US equity market hours are treated as weekdays 9:30 to 16:00 America/New_York.
- US market holidays are not modeled. On a holiday the app may label a price as Live during those clock hours even though the exchange is closed.
