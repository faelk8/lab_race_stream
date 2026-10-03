# ExecPlan Standard

Use this document as the template for implementation plans in RaceStream Lab.

## Purpose

An ExecPlan is required for work that:

- spans multiple services;
- changes architecture;
- introduces infrastructure;
- changes event contracts;
- introduces a new stream engine;
- introduces persistence;
- introduces deployment changes;
- performs a significant refactor.

## Required Structure

### 1. Objective

Explain what must be delivered and what observable behavior proves completion.

### 2. Scope

Explicitly state what is included and excluded.

### 3. Current State

Describe the repository and behavior before the change.

### 4. Target Architecture

Describe the affected components and data flow.

### 5. Contracts

List event schemas, APIs, database tables, ports/interfaces, and compatibility constraints.

### 6. Implementation Steps

Use small ordered milestones that can be independently validated.

### 7. Testing Strategy

Include unit, contract, integration, and end-to-end checks as applicable.

### 8. Validation Commands

List commands expected to run successfully.

### 9. Risks

List likely failure modes, architectural risks, and rollback options.

### 10. Decisions

Record decisions made while implementing the plan.

### 11. Progress

Maintain a checklist with completed and remaining tasks.

## Rules

- Keep the plan synchronized with implementation.
- Do not hide unresolved decisions.
- Prefer a small validated milestone over a large speculative implementation.
- When a decision changes architecture, create an ADR.
- Do not mark a milestone complete without validation evidence.
