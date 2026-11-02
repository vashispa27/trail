"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Old Trail-Link trailers point at /#/<repo>/session/<id>; send them to /repos/<repo>/session/<id>. */
export function HashRedirect() {
  const router = useRouter();
  useEffect(() => {
    if (location.hash.startsWith("#/")) router.replace("/repos/" + location.hash.slice(2));
  }, [router]);
  return null;
}
