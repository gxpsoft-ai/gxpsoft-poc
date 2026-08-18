"""Governed Tool Gateway providing policy validation, rate control, and audit logging."""

import time
from typing import Any, Callable, Dict, Optional, Tuple

from gxpsoft.core.policy import PolicyEngine, PolicyViolationError
from gxpsoft.core.repository import repo
from gxpsoft.models.agent_run import ToolCall
from gxpsoft.models.enums import ActionClass, AuthorType
from gxpsoft.tools.registry import (
    find_similar_deviations,
    get_batch_genealogy,
    get_equipment_calibration,
    get_operator_training,
    search_sops,
    stage_investigation_draft,
)


class ToolGatewayError(Exception):
    """Raised when tool execution or resolution fails."""
    pass


# Map of tool_name -> (Callable, ActionClass, Version)
TOOL_DEFINITIONS: Dict[str, Tuple[Callable[..., Any], ActionClass, str]] = {
    "search_sops": (search_sops, ActionClass.A0_OBSERVE, "1.0"),
    "get_equipment_calibration": (get_equipment_calibration, ActionClass.A0_OBSERVE, "1.0"),
    "get_batch_genealogy": (get_batch_genealogy, ActionClass.A0_OBSERVE, "1.0"),
    "get_operator_training": (get_operator_training, ActionClass.A0_OBSERVE, "1.0"),
    "find_similar_deviations": (find_similar_deviations, ActionClass.A0_OBSERVE, "1.0"),
    "stage_investigation_draft": (stage_investigation_draft, ActionClass.A2_PREPARE, "1.0"),
}


class ToolGateway:
    """Governed interceptor executing tools with strict GxP policy checks and provenance."""

    @staticmethod
    def invoke(
        tool_name: str,
        arguments: Dict[str, Any],
        agent_run_id: str,
        actor_id: str,
        actor_type: AuthorType = AuthorType.AGENT,
        case_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validates policy, executes the tool, and creates an immutable ToolCall audit record."""
        tool_entry = TOOL_DEFINITIONS.get(tool_name)
        if not tool_entry:
            raise ToolGatewayError(f"Tool '{tool_name}' is not registered in the Governed Tool Gateway.")

        func, action_class, tool_version = tool_entry

        # 1. Policy Engine Guardrail Check
        PolicyEngine.validate_action(
            action_class=action_class,
            actor_type=actor_type,
            actor_id=actor_id
        )

        start_time = time.perf_counter()
        policy_decision = "ALLOWED"

        try:
            # 2. Execute tool
            result = func(**arguments)
        except Exception as e:
            policy_decision = f"EXECUTION_FAILED: {str(e)}"
            raise ToolGatewayError(f"Error executing tool '{tool_name}': {str(e)}") from e
        finally:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            # 3. Create ToolCall record
            tool_call = ToolCall(
                agent_run_id=agent_run_id,
                tool_name=tool_name,
                tool_version=tool_version,
                request_payload=arguments,
                response_payload=result if "result" in locals() else {"error": policy_decision},
                policy_decision=policy_decision,
                latency_ms=elapsed_ms
            )

            # 4. Append to Audit Ledger
            repo.audit_ledger.append(
                event_type="TOOL_INVOKED",
                entity_type="ToolCall",
                entity_id=tool_call.tool_call_id,
                actor_id=actor_id,
                actor_type=actor_type,
                data_snapshot={
                    "tool_name": tool_name,
                    "agent_run_id": agent_run_id,
                    "action_class": action_class.value,
                    "latency_ms": elapsed_ms,
                    "policy_decision": policy_decision
                },
                case_id=case_id
            )

        return result
