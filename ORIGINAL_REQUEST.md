# Original User Request

## 2026-08-14T21:25:02Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: [none — teamwork routes from the description]

Set up and deploy a continuously running agent system featuring OpenHuman and Hermes models, integrated with Telegram for messaging, and connected to an Obsidian vault for knowledge management. The system must operate entirely on a free-tier cloud platform.

Working directory: ~/teamwork_projects/openhuman_hermes_bot
Integrity mode: development

## Requirements

### R1. Core Integration & Logic
Deploy a Telegram bot integrated with an OpenHuman and Hermes agent pipeline. The agents must be able to read and write to an Obsidian knowledge base.

### R2. Cloud Deployment Strategy
The system must be configured to deploy on a free-tier cloud service so it runs continuously without relying on the user's local machine.

### R3. Obsidian Synchronization
Establish a mechanism for the cloud-hosted agents to sync with the user's Obsidian vault since it cannot rely on direct local file access.

## Acceptance Criteria

### Integration & Logic
- [ ] A test script successfully mocks a Telegram message, passes it to the agent pipeline, and asserts that a response is generated.
- [ ] A test script successfully verifies that the agent pipeline can read a sample note from a mock Obsidian vault directory and write a new note to it.

### Deployment & Sync
- [ ] A deployment configuration file (e.g., Dockerfile) is provided and successfully builds the environment.
- [ ] An automated test or script demonstrates that the system can pull updates from and push changes to a remote repository (representing the remote Obsidian vault).
