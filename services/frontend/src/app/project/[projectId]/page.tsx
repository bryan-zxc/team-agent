"use client";

import { useParams } from "next/navigation";
import { Workbench } from "@/components/workbench/Workbench";

export default function ProjectPage() {
  const params = useParams<{ projectId: string }>();

  return <Workbench projectId={params.projectId} />;
}
