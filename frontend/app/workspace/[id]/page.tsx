"use client";

import Workspace from "@/components/Workspace";
import { useParams } from "next/navigation";

export default function WorkspacePage() {
  const params = useParams<{ id: string }>();
  return <Workspace sessionId={params.id} />;
}
