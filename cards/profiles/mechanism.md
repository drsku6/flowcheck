# Profile: mechanism (DRAFT — table never arrived; correct me)

For how-it-works text: causal chains where each stage enables the next.

- Node roles: START names the system; steps are causal stages; outputs are products; TAKE is the net effect.
- Diamonds mean alternative pathways the source states (e.g. light vs dark, aerobic vs anaerobic).
- Edge labels name the trigger or condition routing flow down a path.
- Bullets: entities, inputs consumed, outputs released, locations.

```mermaid
flowchart LR
n1(["<b>System</b><br/>• Setting"]):::startNode
n2{"Which path?"}:::decisionNode
n3(["<b>Path A</b><br/>• Converts X"]):::altDx
n4(["<b>Product</b><br/>• Net yield"]):::dispoNode
n1 --> n2
n2 -->|"Light"| n3
n2 -->|"Dark"| n4
n3 --> n4
```
