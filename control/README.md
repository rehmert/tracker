# Tracker release command queue

The DEV-only release agent reads `control/current.json`. Only a `proceed` action from the user through the connected GitHub workflow should publish one new pinned command. Do not commit medical data, logs, credentials or arbitrary shell commands. A command has a unique request ID and advances one reviewed stage; no code in this branch is ever deployed.
