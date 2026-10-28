# Profile: rules

For normative text: who must do what, by when, and what happens otherwise.
Boards grammar: applicability first — route by whether the rule fires.

- START names the rule system and its scope, 2–4 bullets.
- Diamonds are applicability conditions and exceptions the source states, numbered broad to specific.
- Edge labels name the if-applies / if-exempt outcome.
- Bullets carry actors, deadlines, amounts, filings, consequences. Every number exact.
- Each fact once; the compliance summary closes the chart; TAKE states it in one line.

```mermaid
flowchart LR
n1(["<b>Filing rule</b><br/>• Who it covers<br/>• Annual deadline"]):::startNode
n2{"1. Applies?"}:::decisionNode
n3(["<b>Comply</b><br/>• File by the date<br/>• Keep proof")]:::altDx
n4(["<b>Result</b><br/>• Late filing draws penalty"]):::dispoNode
n1 --> n2
n2 -->|"Covered"| n3
n2 -->|"Exempt"| n4
n3 --> n4
```
