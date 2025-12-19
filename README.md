# VeCTRL
VeCTRL is a vector-driven control architecture for real-time agents. It combines high-dimensional sensory embeddings, memory-based retrieval, and adaptive action selection inside a closed-loop controller.


## Control Loop

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
