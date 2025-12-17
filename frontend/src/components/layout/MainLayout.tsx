"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useClerk, useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { Folder, LogOut, Menu, MessageSquare, Video, Shield } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

const navigation = [
  { name: "Videos", href: "/videos", icon: Video },
  { name: "Collections", href: "/collections", icon: Folder },
  { name: "Conversations", href: "/conversations", icon: MessageSquare },
];

const adminNavigation = [
  { name: "Admin", href: "/admin", icon: Shield },
];

export const MainLayout = ({ children }: { children: React.ReactNode }) => {
  const pathname = usePathname();
  const { user: clerkUser, isLoaded, isSignedIn } = useUser();
  const { signOut } = useClerk();

  const displayName =
    clerkUser?.fullName || clerkUser?.primaryEmailAddress?.emailAddress;
  const email = clerkUser?.primaryEmailAddress?.emailAddress;

  // Check if user is admin (stored in Clerk public metadata)
  const isAdmin = clerkUser?.publicMetadata?.is_superuser === true;

  const handleLogout = () => {
    signOut({ redirectUrl: "/sign-in" });
  };

  const renderNav = (includeAdmin = false) => {
    const allNavigation = includeAdmin && isAdmin
      ? [...navigation, ...adminNavigation]
      : navigation;

    return allNavigation.map((item) => {
      const Icon = item.icon;
      const isActive = pathname.startsWith(item.href);
      return (
        <Link
          key={item.name}
          href={item.href}
          className={cn(
            "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive
              ? "bg-primary/10 text-foreground"
              : "text-muted-foreground hover:text-foreground",
            item.icon === Shield && "border-t mt-2 pt-4"
          )}
        >
          <span className="flex items-center gap-2">
            <Icon className="h-4 w-4" />
            {item.name}
          </span>
        </Link>
      );
    });
  };

  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (!isSignedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-muted-foreground">Please sign in to continue.</p>
          <Button onClick={() => (window.location.href = "/sign-in")}>Sign in</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen w-full bg-muted/40">
      <aside className="hidden w-64 flex-col border-r bg-background/90 lg:flex">
        <div className="flex h-16 items-center border-b px-6 text-lg font-semibold">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <span className="text-sm font-bold">RT</span>
            </div>
            <span className="text-base font-semibold">RAG Transcript</span>
          </Link>
        </div>
        <nav className="flex-1 space-y-1 px-4 py-6">{renderNav(true)}</nav>
        {clerkUser && (
          <div className="border-t px-4 py-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">{displayName}</p>
            {email && <p>{email}</p>}
            <Button
              variant="ghost"
              size="sm"
              className="mt-3 w-full justify-start gap-2"
              onClick={handleLogout}
            >
              <LogOut className="h-4 w-4" />
              Logout
            </Button>
          </div>
        )}
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-16 items-center gap-3 border-b bg-background px-4 lg:px-6">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle navigation</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="flex flex-col">
              <div className="flex h-16 items-center border-b text-lg font-semibold">
                <span>RAG Transcript</span>
              </div>
              <nav className="flex-1 space-y-1 py-6">{renderNav(true)}</nav>
              {clerkUser && (
                <div className="border-t pt-4 text-sm text-muted-foreground">
                  <p className="font-medium text-foreground">{displayName}</p>
                  {email && <p>{email}</p>}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 w-full justify-start gap-2"
                    onClick={handleLogout}
                  >
                    <LogOut className="h-4 w-4" />
                    Logout
                  </Button>
                </div>
              )}
            </SheetContent>
          </Sheet>
          <Separator orientation="vertical" className="mr-2 hidden h-6 lg:block" />
          <div className="flex flex-1 items-center justify-between">
            <div className="text-sm text-muted-foreground">
              {pathname === "/" ? "Overview" : pathname.replace("/", "").split("/")[0]}
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              {clerkUser && (
                <Button
                  variant="outline"
                  size="sm"
                  className="hidden gap-2 sm:inline-flex"
                  onClick={handleLogout}
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </Button>
              )}
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto bg-background px-4 py-6 lg:px-8 lg:py-10">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
};
