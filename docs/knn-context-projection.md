Here’s a clean, structured Markdown document you can drop directly into your VeCTRL docs.

⸻


# VeCTRL Architecture: Global–Local KNN with Context Projection

## Overview

This document describes a scalable architecture for VeCTRL systems where:

- A **central coordinator (laptop / Pi)** operates over a **high-dimensional global state**
- Multiple **edge devices (ESP32, etc.)** operate over **lower-dimensional local state**
- **KNN + Q-learning** is used at both levels, but over *different representations*

The key idea:

> Edge devices do **not** operate over the full global embedding space.  
> Instead, they operate over **local state augmented with compact context from the global system**.

---

## Problem Statement

In a multi-device robotics system:

- The global system observes:
  - vision
  - multiple actuators
  - task phase
  - world state

- Each edge device observes:
  - only its local sensors
  - limited signals

### Challenge

How can an edge device perform meaningful KNN selection when:

- Global candidates are high-dimensional
- Edge devices only see a subset of those dimensions

---

## Core Solution

Instead of using global candidates directly:

### ❌ Incorrect Approach
- Truncate global vectors
- Run KNN on partial data

This causes **state aliasing**:
> Different global situations appear identical locally → wrong actions

---

### ✅ Correct Approach

Each edge device operates on:

\[
\textbf{Local State + Global Context}
\]

Where:

- **Local state** = directly observed signals
- **Global context** = compressed, task-relevant information from the laptop

---

## System Architecture

```mermaid
flowchart TD

    subgraph Laptop
        G1[Global State Fusion]
        G2[High-Dim KNN / Policy]
        G3[Skill & Phase Selection]
        G4[Context Generation]
    end

    subgraph Edge_A["Edge Device A (Arm)"]
        A1[Local Sensors]
        A2[Local + Context State]
        A3[KNN + Q Selection]
        A4[Servo Output]
    end

    subgraph Edge_B["Edge Device B (Gripper)"]
        B1[Local Sensors]
        B2[Local + Context State]
        B3[KNN + Q Selection]
        B4[Actuation]
    end

    G1 --> G2
    G2 --> G3
    G3 --> G4

    G4 --> A2
    G4 --> B2

    A1 --> A2
    A2 --> A3
    A3 --> A4

    B1 --> B2
    B2 --> B3
    B3 --> B4


⸻

Global State (Laptop)

The laptop maintains a high-dimensional representation:

GlobalState = {
    "object_x": float,
    "object_y": float,
    "object_size": float,
    "arm_angle": float,
    "arm_velocity": float,
    "gripper_open": float,
    "target_distance": float,
    "alignment_error": float,
    "task_phase": int,
    "contact_confidence": float
}

This state is used for:
	•	skill selection
	•	phase transitions
	•	coordination across devices
	•	high-dimensional KNN or policy evaluation

⸻

Context Packets

The laptop sends compact context packets to each edge device.

Arm Context

ArmContext = {
    "skill_id": int,
    "phase_id": int,
    "target_delta_angle": float,
    "motion_mode": int  # e.g. FAST, PRECISE, HOLD
}


⸻

Gripper Context

GripperContext = {
    "skill_id": int,
    "phase_id": int,
    "close_command_bias": float,
    "grasp_readiness": float
}


⸻

Local State (Edge Devices)

Arm Local State

ArmLocalState = {
    "angle": float,
    "velocity": float
}


⸻

Gripper Local State

GripperLocalState = {
    "open_amount": float,
    "contact_signal": float
}


⸻

Edge KNN Input Vectors

Each edge constructs a combined state vector:

⸻

Arm KNN Vector

ArmStateVector = [
    angle,
    velocity,
    target_delta_angle,
    phase_id,
    motion_mode
]


⸻

Gripper KNN Vector

GripperStateVector = [
    open_amount,
    contact_signal,
    phase_id,
    close_command_bias,
    grasp_readiness
]


⸻

Candidate Representation

Each edge device maintains a local candidate set:

Candidate = {
    "state": List[float],
    "action": int,
    "q_value": float
}


⸻

Example (Arm)

[
    {
        "state": [38, 0, -8, 1, 0],
        "action": +1,
        "q_value": 0.72
    },
    {
        "state": [41, 1, -5, 1, 0],
        "action": -1,
        "q_value": 0.89
    }
]


⸻

Example (Gripper)

[
    {
        "state": [0.95, 0.05, 1, 0, 0.8],
        "action": "HOLD_OPEN",
        "q_value": 0.91
    },
    {
        "state": [0.90, 0.20, 2, 1, 1.0],
        "action": "CLOSE_SMALL",
        "q_value": 0.85
    }
]


⸻

Control Loop

Step 1: Edge → Laptop

Each edge sends local summaries:

{
    "arm_angle": 40,
    "arm_velocity": 1
}

{
    "gripper_open": 0.95,
    "contact_signal": 0.1
}


⸻

Step 2: Laptop Processing

Laptop builds global state and selects:
	•	skill
	•	phase
	•	per-edge context

⸻

Step 3: Laptop → Edge

Laptop sends context packets:

# Arm
{
    "phase_id": 1,
    "target_delta_angle": -6,
    "motion_mode": 0
}

# Gripper
{
    "phase_id": 1,
    "close_command_bias": 0,
    "grasp_readiness": 0.8
}


⸻

Step 4: Edge Local Decision

Each edge:
	1.	Builds local state vector
	2.	Performs KNN lookup
	3.	Selects action (e.g. argmax Q or ε-greedy)
	4.	Executes immediately

⸻

Key Insight

The edge does not need the full global state.
It needs a sufficient statistic of that state.

This is achieved via:
	•	skill id
	•	phase id
	•	target deltas
	•	compact coordination signals

⸻

Why This Works

Avoids State Aliasing

Without context:

[angle=40, velocity=1]

Could correspond to many global situations.

With context:

[40, 1, -6, phase=align]

Now the state is disambiguated.

⸻

Enables Scalability
	•	Edge devices remain lightweight
	•	Global system handles complexity
	•	Communication bandwidth stays low
	•	Real-time control remains stable

⸻

Design Principle

For each edge device:

Define the minimum context needed to make the local control problem approximately Markov.

⸻

Summary

Laptop
	•	High-dimensional reasoning
	•	Skill selection
	•	Global coordination
	•	Context generation

Edge Devices
	•	Low-dimensional control
	•	Fast KNN lookup
	•	Local Q updates
	•	Immediate actuation

⸻

Future Extensions
	•	Learned context embeddings instead of hand-designed fields
	•	Dynamic candidate set generation per skill
	•	Hierarchical Q-learning across layers
	•	Multi-device coordination policies

⸻

Takeaway

VeCTRL is not about sharing one giant embedding space across all devices.

It is about:

Projecting global intelligence into local, actionable representations.

---