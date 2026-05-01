import { StrictMode, createElement, type JSX, type PropsWithChildren } from 'react'
import { ClerkFailed, ClerkLoaded, ClerkLoading, ClerkProvider } from '@clerk/react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import './index.css'
import { AuthProvider } from './lib/auth-provider'
import { router } from './router'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {createElement(
      ClerkProvider as unknown as (props: PropsWithChildren<{ afterSignOutUrl?: string }>) => JSX.Element,
      { afterSignOutUrl: '/login' },
      <>
        <ClerkLoading>
          <div className="flex min-h-screen items-center justify-center px-4">
            <div className="rounded-2xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-500 shadow-sm">
              正在加载登录服务...
            </div>
          </div>
        </ClerkLoading>
        <ClerkFailed>
          <div className="flex min-h-screen items-center justify-center px-4">
            <div className="max-w-md rounded-2xl border border-rose-200 bg-rose-50 px-6 py-5 text-sm leading-6 text-rose-700 shadow-sm">
              无法加载 Clerk 登录服务。请检查网络是否能访问 Clerk，并刷新页面重试。
            </div>
          </div>
        </ClerkFailed>
        <ClerkLoaded>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </ClerkLoaded>
      </>,
    )}
  </StrictMode>,
)
