"""
OpenDesktop - Orchestrator
Coordinates multi-agent campaigns across fleet of sandbox machines.
Uses the agent runner for task execution.
"""
import os
import asyncio
from typing import Optional, Callable

from .docker_manager import sandbox_manager
from .agent_runner import agent_runner


VAULT_PATH = "/Users/chrisschofield/workspace/open-orgo/ObsidianVault"


class FleetOrchestrator:
    """
    Orchestrates campaigns across multiple sandbox machines.
    Can run a single-machine task or a multi-agent fleet campaign.
    """

    async def run_single_task(
        self,
        machine_id: str,
        prompt: str,
        broadcast_action: Optional[Callable] = None
    ):
        """Run an agent task on a single machine."""
        result = await agent_runner.run_task(
            sandbox_id=machine_id,
            prompt=prompt,
            sandbox_manager=sandbox_manager,
            broadcast_action=broadcast_action,
        )

        # Save result to Obsidian vault
        os.makedirs(VAULT_PATH, exist_ok=True)
        safe_name = prompt[:50].replace(" ", "_").replace("/", "_")
        filepath = os.path.join(VAULT_PATH, f"{safe_name}_report.md")
        try:
            with open(filepath, "w") as f:
                f.write(f"# Agent Task Report\n\n")
                f.write(f"**Prompt:** {prompt}\n\n")
                f.write(f"**Machine:** {machine_id}\n\n")
                f.write(f"**Status:** {result.get('status', 'unknown')}\n\n")
                f.write(f"**Steps:** {result.get('steps', 0)}\n\n")
                f.write(f"**Summary:** {result.get('summary', 'N/A')}\n")
        except Exception as e:
            print(f"[Orchestrator] Failed to save vault note: {e}")

        return result

    async def run_fleet_campaign(
        self,
        prompt: str,
        broadcast_action: Optional[Callable] = None
    ):
        """
        Provision multiple machines and run coordinated tasks.
        Machine 1: Main browser agent (does the primary task)
        Machine 2: Research support (searches for relevant info)
        """
        if broadcast_action:
            await broadcast_action("fleet", {
                "type": "action",
                "step": 0,
                "thought": f"Fleet campaign starting: {prompt}",
                "action_type": "fleet_start",
                "agent": "Fleet Orchestrator",
                "machine_id": "fleet",
            })

        # Create machines
        machines = []
        roles = [
            ("Primary Agent", f"Complete this task: {prompt}"),
            ("Research Agent", f"Open Chromium and search the web for information related to: {prompt}. Take notes on what you find."),
        ]

        for name, task in roles:
            machine_data = await sandbox_manager.create_sandbox(name=name)
            machines.append((machine_data["id"], task))

            if broadcast_action:
                await broadcast_action(machine_data["id"], {
                    "type": "action",
                    "step": 0,
                    "thought": f"Provisioned machine: {name} ({machine_data['id']})",
                    "action_type": "provision",
                    "agent": "Fleet Orchestrator",
                    "machine_id": machine_data["id"],
                })

        # Wait for machines to be healthy
        await asyncio.sleep(10)

        # Run agents in parallel
        tasks = []
        for machine_id, task_prompt in machines:
            tasks.append(
                agent_runner.run_task(
                    sandbox_id=machine_id,
                    prompt=task_prompt,
                    sandbox_manager=sandbox_manager,
                    broadcast_action=broadcast_action,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        if broadcast_action:
            await broadcast_action("fleet", {
                "type": "action",
                "step": 99,
                "thought": f"Fleet campaign complete. {len(machines)} machines finished.",
                "action_type": "fleet_complete",
                "agent": "Fleet Orchestrator",
                "machine_id": "fleet",
            })

        return {"status": "completed", "machines": len(machines), "results": str(results)}


orchestrator = FleetOrchestrator()
