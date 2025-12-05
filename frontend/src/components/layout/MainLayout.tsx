'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Video, MessageSquare, LogOut, Folder, Menu, X } from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth';
import { useState } from 'react';
import { Button } from '@/components/shared';

/**
 * MainLayout - Main application layout with navigation
 * Uses Mindful Learning theme tokens for consistent design
 */
export const MainLayout = ({ children }: { children: React.ReactNode }) => {
  const pathname = usePathname();
  const { user, clearAuth } = useAuthStore();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const navigation = [
    { name: 'Videos', href: '/videos', icon: Video },
    { name: 'Collections', href: '/collections', icon: Folder },
    { name: 'Conversations', href: '/conversations', icon: MessageSquare },
  ];

  const handleLogout = () => {
    clearAuth();
    window.location.href = '/login';
  };

  return (
    <div className="min-h-screen bg-bg-primary">
      {/* Navigation Header */}
      <nav className="bg-bg-secondary border-b border-border-default shadow-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo and Brand */}
            <div className="flex items-center gap-8">
              <Link href="/" className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                  <span className="text-bg-primary font-bold text-sm">✦</span>
                </div>
                <h1 className="text-lg font-semibold text-text-primary hidden sm:inline">
                  Synth Stack
                </h1>
              </Link>

              {/* Desktop Navigation */}
              <div className="hidden sm:flex sm:gap-1">
                {navigation.map((item) => {
                  const Icon = item.icon;
                  const isActive = pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={`
                        inline-flex items-center gap-2 px-4 py-2 rounded-lg
                        text-sm font-medium transition-all duration-200 ease-smooth
                        ${
                          isActive
                            ? 'bg-primary-50 text-primary border border-primary-100'
                            : 'text-text-secondary hover:bg-bg-tertiary border border-transparent'
                        }
                      `}
                    >
                      <Icon className="w-4 h-4" />
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            </div>

            {/* Right side: User info and Logout */}
            <div className="flex items-center gap-4">
              {user && (
                <div className="hidden md:flex items-center gap-3">
                  <div className="flex flex-col items-end">
                    <span className="text-sm font-medium text-text-primary">
                      {user.email?.split('@')[0]}
                    </span>
                    <span className="text-xs text-text-muted">Learning</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleLogout}
                    className="gap-2"
                  >
                    <LogOut className="w-4 h-4" />
                    <span className="hidden sm:inline">Logout</span>
                  </Button>
                </div>
              )}

              {/* Mobile Menu Button */}
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="md:hidden p-2 text-text-primary hover:bg-bg-tertiary rounded-lg transition-colors"
              >
                {isMobileMenuOpen ? (
                  <X className="w-6 h-6" />
                ) : (
                  <Menu className="w-6 h-6" />
                )}
              </button>
            </div>
          </div>

          {/* Mobile Navigation Menu */}
          {isMobileMenuOpen && (
            <div className="sm:hidden pb-4 border-t border-border-default mt-2">
              <div className="flex flex-col gap-2">
                {navigation.map((item) => {
                  const Icon = item.icon;
                  const isActive = pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      onClick={() => setIsMobileMenuOpen(false)}
                      className={`
                        flex items-center gap-3 px-4 py-3 rounded-lg
                        text-sm font-medium transition-colors
                        ${
                          isActive
                            ? 'bg-primary-50 text-primary'
                            : 'text-text-secondary hover:bg-bg-tertiary'
                        }
                      `}
                    >
                      <Icon className="w-4 h-4" />
                      {item.name}
                    </Link>
                  );
                })}
                {user && (
                  <div className="border-t border-border-default pt-3 mt-2">
                    <div className="px-4 py-2 mb-3">
                      <p className="text-sm font-medium text-text-primary">
                        {user.email}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setIsMobileMenuOpen(false);
                        handleLogout();
                      }}
                      className="w-full justify-start gap-2"
                    >
                      <LogOut className="w-4 h-4" />
                      Logout
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
};
