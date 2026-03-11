"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { IDockviewPanelProps } from "dockview";
import { apiFetch } from "@/lib/api";
import { MemberProfile } from "@/components/members/MemberProfile";
import { MemberProfileEditor } from "@/components/members/MemberProfileEditor";
import { CostCard } from "@/components/members/CostCard";
import type { MemberCosts } from "@/types";

type Params = {
  projectId: string;
  memberId: string;
  memberName: string;
  memberType: "human" | "ai" | "coordinator";
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function MemberProfileTab({ params }: IDockviewPanelProps<Params>) {
  const { projectId, memberId, memberName, memberType } = params;
  const [content, setContent] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [costs, setCosts] = useState<MemberCosts | null>(null);
  const marginTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isAiMember = memberType === "ai" || memberType === "coordinator";

  useEffect(() => {
    apiFetch(`/projects/${projectId}/members/${memberId}/profile`)
      .then((r) => r.json())
      .then((data) => setContent(data.content ?? ""));
  }, [projectId, memberId]);

  useEffect(() => {
    if (!isAiMember) return;
    apiFetch(`/projects/${projectId}/members/${memberId}/costs`)
      .then((r) => r.json())
      .then((data) => setCosts(data));
  }, [projectId, memberId, isAiMember]);

  const handleMarginChange = useCallback(
    (margin: number) => {
      setCosts((prev) =>
        prev ? { ...prev, margin_percent: margin, nsr: prev.total_cost * (1 + margin / 100) } : prev,
      );
      if (marginTimer.current) clearTimeout(marginTimer.current);
      marginTimer.current = setTimeout(() => {
        apiFetch(`/projects/${projectId}/members/${memberId}/margin`, {
          method: "PUT",
          body: JSON.stringify({ margin_percent: margin }),
        });
      }, 600);
    },
    [projectId, memberId],
  );

  const handleSave = useCallback(
    async (draft: string) => {
      await apiFetch(`/projects/${projectId}/members/${memberId}/profile`, {
        method: "PUT",
        body: JSON.stringify({ content: draft }),
      });
      setContent(draft);
      setEditing(false);
    },
    [projectId, memberId],
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
      costCard={
        isAiMember && costs ? (
          <CostCard
            totalCost={costs.total_cost}
            middleStat={{ label: "Tokens", value: formatTokens(costs.total_tokens) }}
            marginPercent={costs.margin_percent}
            onMarginChange={handleMarginChange}
          />
        ) : undefined
      }
    />
  );
}
