import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './app/layouts/AppLayout'
import { ProtectedRoute } from './app/ProtectedRoute'
import {
  AnalyticsRoute,
  ManageUsersRoute,
  SuperAdminRoute,
  UploadRoute,
} from './app/RoleRoutes'
import { ToastContainer } from './components/ToastContainer'
import { AnalyticsPage } from './features/analytics/AnalyticsPage'
import { AccessDeniedPage, ForbiddenPage, NotFoundPage } from './features/auth/ErrorPages'
import { LoginPage } from './features/auth/LoginPage'
import { ProfilePage } from './features/auth/ProfilePage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { DepartmentsPage } from './features/departments/DepartmentsPage'
import { DocumentDetailPage } from './features/documents/DocumentDetailPage'
import { DocumentsPage } from './features/documents/DocumentsPage'
import { UploadPage } from './features/documents/UploadPage'
import { AskPage } from './features/rag/AskPage'
import { HistoryPage } from './features/rag/HistoryPage'
import { AdminsPage } from './features/users/AdminsPage'
import { UsersPage } from './features/users/UsersPage'
import { AuthProvider, useAuth } from './hooks/useAuth'
import { ToastProvider } from './hooks/useToast'

function HomeRedirect() {
  const { user, loading } = useAuth()
  if (loading) return null
  return <Navigate to={user ? '/dashboard' : '/login'} replace />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/access-denied" element={<AccessDeniedPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route element={<UploadRoute />}>
            <Route path="/documents/upload" element={<UploadPage />} />
          </Route>
          <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/profile" element={<ProfilePage />} />

          <Route element={<SuperAdminRoute />}>
            <Route path="/admin/departments" element={<DepartmentsPage />} />
            <Route path="/admin/admins" element={<AdminsPage />} />
          </Route>
          <Route element={<ManageUsersRoute />}>
            <Route path="/admin/users" element={<UsersPage />} />
          </Route>
          <Route element={<AnalyticsRoute />}>
            <Route path="/analytics" element={<AnalyticsPage />} />
          </Route>

          <Route path="/forbidden" element={<ForbiddenPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
          <ToastContainer />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
