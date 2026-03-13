"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { IDockviewPanelProps } from "dockview";
import { apiFetch } from "@/lib/api";
import { MemberProfile } from "@/components/members/MemberProfile";
import { MemberProfileEditor } from "@/components/members/MemberProfileEditor";
import { CostCard } from "@/components/members/CostCard";
import { HumanCostCard } from "@/components/members/HumanCostCard";
import { TimeCards } from "@/components/members/TimeCards";
import type { HumanCosts, MemberActiveTime, MemberCosts } from "@/types";

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
  const [humanCosts, setHumanCosts] = useState<HumanCosts | null>(null);
  const [activeTime, setActiveTime] = useState<MemberActiveTime | null>(null);
  const marginTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rateTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isAiMember = memberType === "ai" || memberType === "coordinator";
  const isHuman = memberType === "human";

  // AI members: fetch profile
  useEffect(() => {
    if (!isAiMember) return;
    apiFetch(`/projects/${projectId}/members/${memberId}/profile`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load profile");
        return r.json();
      })
      .then((data) => setContent(data.content ?? ""))
      .catch(() => setContent(""));
  }, [projectId, memberId, isAiMember]);

  // AI members: fetch costs
  useEffect(() => {
    if (!isAiMember) return;
    apiFetch(`/projects/${projectId}/members/${memberId}/costs`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load costs");
        return r.json();
      })
      .then((data) => setCosts(data))
      .catch(() => {});
  }, [projectId, memberId, isAiMember]);

  // Human members: fetch costs
  const fetchHumanCosts = useCallback(() => {
    apiFetch(`/projects/${projectId}/members/${memberId}/human-costs`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load costs");
        return r.json();
      })
      .then((data) => setHumanCosts(data))
      .catch(() => {});
  }, [projectId, memberId]);

  useEffect(() => {
    if (!isHuman) return;
    fetchHumanCosts();
  }, [isHuman, fetchHumanCosts]);

  // Human members: fetch active time
  const fetchActiveTime = useCallback(() => {
    apiFetch(`/projects/${projectId}/members/${memberId}/active-time`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load active time");
        return r.json();
      })
      .then((data) => setActiveTime(data))
      .catch(() => {});
  }, [projectId, memberId]);

  useEffect(() => {
    if (!isHuman) return;
    fetchActiveTime();
  }, [isHuman, fetchActiveTime]);

  const handleRefresh = useCallback(() => {
    if (isAiMember) {
      apiFetch(`/projects/${projectId}/members/${memberId}/costs`)
        .then((r) => {
          if (!r.ok) throw new Error("Failed to refresh costs");
          return r.json();
        })
        .then((data) => setCosts(data))
        .catch(() => {});
    }
    if (isHuman) {
      fetchActiveTime();
      fetchHumanCosts();
    }
  }, [projectId, memberId, isAiMember, isHuman, fetchActiveTime, fetchHumanCosts]);

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

  const handleRateChange = useCallback(
    (rate: number) => {
      setHumanCosts((prev) =>
        prev ? { ...prev, rate, nsr: rate * prev.total_hours } : prev,
      );
      if (rateTimer.current) clearTimeout(rateTimer.current);
      rateTimer.current = setTimeout(() => {
        apiFetch(`/projects/${projectId}/members/${memberId}/settings`, {
          method: "PUT",
          body: JSON.stringify({ settings: { rate } }),
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

  // AI members wait for profile content; humans render immediately
  if (isAiMember && content === null) return null;

  if (editing && content !== null) {
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
      content={isAiMember ? content ?? undefined : undefined}
      onEdit={isAiMember ? () => setEditing(true) : undefined}
      onRefresh={handleRefresh}
      costCard={
        isAiMember && costs ? (
          <CostCard
            totalCost={costs.total_cost}
            middleStat={{ label: "Tokens", value: formatTokens(costs.total_tokens) }}
            marginPercent={costs.margin_percent}
            onMarginChange={handleMarginChange}
          />
        ) : isHuman && humanCosts ? (
          <HumanCostCard
            rate={humanCosts.rate}
            totalHours={humanCosts.total_hours}
            avgMarkupPercent={humanCosts.avg_markup_percent}
            onRateChange={handleRateChange}
          />
        ) : undefined
      }
      timeCards={
        isHuman && activeTime ? (
          <TimeCards
            todayMinutes={activeTime.today_minutes}
            weekMinutes={activeTime.week_minutes}
            lifetimeMinutes={activeTime.lifetime_minutes}
          />
        ) : undefined
      }
    />
  );
}
