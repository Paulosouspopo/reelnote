import { redirect } from "next/navigation";

import { Inbox } from "@/components/Inbox";
import { getUserId } from "@/lib/supabase/server";

export default async function HomePage() {
  const userId = await getUserId();
  if (!userId) redirect("/login");
  return <Inbox userId={userId} />;
}
