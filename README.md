# VeCTRL
VeCTRL is a vector-driven control architecture for real-time agents. It combines high-dimensional sensory embeddings, memory-based retrieval, and adaptive action selection inside a closed-loop controller.

## Levels of Control
1. LLM Policy: Creates loss functions mapped to concrete goals ("move forward," "stop,", "dance")
2. Online vector-based Q Learning for VeCTRL Core
3. Offline creation of new high-dimensional points for VeCTRL Core, allowing for adaptive pattern definition

## Control Loop

```mermaid
flowchart LR
  %% VeCTRL: Vector-driven Control Loop

  S([Sensors<br/>n-dim signals])
  E[[Embed / Window<br/>→ v⃗_t]]
  M[(Vector Memory<br/>ANN / kNN)]
  P{{Policy / Selector<br/>argmax / sample}}
  A([Actuators<br/>m-dim impulses])

  %% Main flow
  S --> E --> P --> A

  %% Memory retrieval + writeback
  E -->|query| M
  M -->|neighbors| P
  A -->|feedback: new sensory input| S

  %% Learning / rescoring (optional but on-brand)
  A -.->|reward / loss / TD error| M

```

### Core Loop

        ┌────────────┐
        │  Sensors   │
        └─────┬──────┘
              │  n-dim vector
              ▼
        ┌────────────┐
        │  Embedding │
        │  / Memory  │◄───┐
        └─────┬──────┘    │
              │ kNN / ANN │ feedback
              ▼           │
        ┌────────────┐    │
        │ Action /   │────┘
        │ Control    │
        └─────┬──────┘
              │ m-dim impulses
              ▼
        ┌────────────┐
        │  Actuators │
        └────────────┘

### Outside the Loop

        ┌───────────┐
        │   LLM     │
        │ Planner   │
        └─────┬─────┘
              │
          (sets goals)
              │
        ┌─────▼─────┐
        │  VeCTRL   │  ← unchanged core
        └───────────┘
