"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    async function checkAuth() {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!session) {
        router.replace("/login");
        return;
      }

      // Check if user has a connection record
      const { data } = await supabase
        .from("connections")
        .select("id")
        .eq("user_id", session.user.id)
        .single();

      if (data) {
        router.replace("/chat");
      } else {
        router.replace("/onboarding");
      }
    }

    checkAuth();
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
    </div>
  );
}
