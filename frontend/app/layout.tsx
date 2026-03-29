import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { AuthProvider } from "@/hooks/useAuth";
import { SmartCalendarProvider } from "@/hooks/useSmartCalendarStore";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";

export const metadata: Metadata = {
  title: "NottFind | 宁诺实习智能匹配平台",
  description: "专为宁波诺丁汉大学学生打造的一站式校园平台：AI 智能实习匹配、校园活动、学习资讯",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen flex flex-col">
        <AuthProvider>
          <SmartCalendarProvider>
            <Suspense fallback={<header className="sticky top-0 z-50 h-16 border-b border-unnc-blue/10 bg-white/95" aria-hidden />}>
              <SiteHeader />
            </Suspense>
            <main className="flex-1">{children}</main>
            <SiteFooter />
          </SmartCalendarProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
