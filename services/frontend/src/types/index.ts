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
  content: string;
  created_at: string;
};

export type User = {
  id: string;
  display_name: string;
  type: string;
};
