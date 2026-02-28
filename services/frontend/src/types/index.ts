export type Project = {
  id: string;
  name: string;
  git_repo_url: string | null;
  default_branch: string | null;
  member_count: number;
  room_count: number;
  is_locked: boolean;
  lock_reason: string | null;
  created_at: string;
};

export type Room = {
  id: string;
  name: string;
  primary_chat_id: string;
  created_at: string;
};

export type Message = {
  id: string;
  chat_id: string;
  member_id: string;
  display_name: string;
  type: "human" | "ai" | "coordinator" | "tool_approval_request";
  content: string;
  created_at: string;
  reply_to_id: string | null;
};

export type ToolApprovalBlock = {
  type: "tool_approval_request";
  approval_request_id: string;
  workload_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  input_summary: string;
  permission_key: string;
  original_content: string | null;
};

export type User = {
  id: string;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
};

export type Member = {
  id: string;
  display_name: string;
  type: "human" | "ai" | "coordinator";
  user_id: string | null;
};

export type AvailableUser = {
  id: string;
  display_name: string;
};

export type MemberProfile = {
  content: string;
};

export type WorkloadChat = {
  id: string;
  workload_id: string;
  title: string;
  description: string;
  status: string;
  permission_mode: "default" | "acceptEdits";
  has_session: boolean;
  owner_name: string | null;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
};

export type WorkloadStatusEvent = {
  _event: "workload_status";
  workload_id: string;
  status: string;
  permission_mode?: "default" | "acceptEdits";
  room_id: string;
  updated_at: string;
};

export type DispatchWorkloadItem = {
  owner: string;
  title: string;
  description: string;
  background_context: string;
  problem: string | null;
  permission_mode: "default" | "acceptEdits";
};

export type DispatchCardBlock = {
  type: "dispatch_card";
  dispatch_id: string;
  chat_id: string;
  workloads: DispatchWorkloadItem[];
};

export type ThinkingBlock = {
  type: "thinking";
  thinking: string;
};

export type ToolUseContentBlock = {
  type: "tool_use";
  tool_use_id: string;
  name: string;
  input: Record<string, unknown>;
};

export type ToolResultContentBlock = {
  type: "tool_result";
  tool_use_id: string;
  content: string | null;
  is_error: boolean | null;
};

export type AgentActivityEvent = {
  _event: "agent_activity";
  chat_id: string;
  workload_id: string;
  phase: string;
  tokens: number;
};

export type TodoItem = {
  content: string;
  activeForm?: string;
  status: "pending" | "in_progress" | "completed";
};

export type Skill = {
  name: string;
  description: string;
  path: string;
};

export type TerminalSession = {
  session_id: string;
  project_id: string | null;
};
