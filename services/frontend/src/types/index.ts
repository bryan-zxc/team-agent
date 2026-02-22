export type Project = {
  id: string;
  name: string;
  git_repo_url: string | null;
  member_count: number;
  room_count: number;
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
  type: "human" | "ai";
  content: string;
  created_at: string;
};

export type User = {
  id: string;
  display_name: string;
};

export type Member = {
  id: string;
  display_name: string;
  type: "human" | "ai";
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
  title: string;
  owner_name: string | null;
  owner_id: string | null;
  created_at: string;
};
