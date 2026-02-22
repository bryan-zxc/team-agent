"use client";

import { useCallback, useEffect, useState } from "react";
import type { IDockviewPanelProps } from "dockview";
import { MemberProfile } from "@/components/members/MemberProfile";
import { MemberProfileEditor } from "@/components/members/MemberProfileEditor";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Params = {
  memberId: string;
  memberName: string;
};

export function MemberProfileTab({ params }: IDockviewPanelProps<Params>) {
  const { memberId, memberName } = params;
  const [content, setContent] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/members/${memberId}/profile`)
      .then((r) => r.json())
      .then((data) => setContent(data.content ?? ""));
  }, [memberId]);

  const handleSave = useCallback(
    async (draft: string) => {
      await fetch(`${API_URL}/members/${memberId}/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: draft }),
      });
      setContent(draft);
      setEditing(false);
    },
    [memberId],
  );

  if (content === null) return null;

  if (editing) {
    return (
      <MemberProfileEditor
        content={content}
        onSave={handleSave}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <MemberProfile
      name={memberName}
      content={content}
      onEdit={() => setEditing(true)}
    />
  );
}
