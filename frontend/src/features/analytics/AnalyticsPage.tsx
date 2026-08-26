import { useEffect, useState } from 'react'
import { dashboardApi } from '../../api/dashboard'
import { departmentsApi } from '../../api/departments'
import { KpiCard } from '../../components/Card'
import { ErrorBanner, LoadingSkeleton, PageHeader, ScopeBanner } from '../../components/PageHeader'
import { useAuth } from '../../hooks/useAuth'
import { isSuperAdmin } from '../../utils/permissions'
import type { Department, DepartmentDashboard, SuperAdminDashboard } from '../../types'

export function AnalyticsPage() {
  const { user } = useAuth()
  const [superDash, setSuperDash] = useState<SuperAdminDashboard | null>(null)
  const [deptDash, setDeptDash] = useState<DepartmentDashboard | null>(null)
  const [departments, setDepartments] = useState<Department[]>([])
  const [selectedDept, setSelectedDept] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        if (isSuperAdmin(user)) {
          const [sd, depts] = await Promise.all([
            dashboardApi.superAdmin(),
            departmentsApi.list(),
          ])
          setSuperDash(sd)
          setDepartments(depts)
          if (depts.length) setSelectedDept(depts[0].department_id)
        } else if (user?.department_ids.length) {
          setSelectedDept(user.department_ids[0])
          const dd = await dashboardApi.department(user.department_ids[0])
          setDeptDash(dd)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load analytics')
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [user])

  useEffect(() => {
    if (!selectedDept || isSuperAdmin(user)) return
    dashboardApi
      .department(selectedDept)
      .then(setDeptDash)
      .catch(() => setDeptDash(null))
  }, [selectedDept, user])

  useEffect(() => {
    if (!selectedDept || !isSuperAdmin(user)) return
    dashboardApi
      .department(selectedDept)
      .then(setDeptDash)
      .catch(() => setDeptDash(null))
  }, [selectedDept, user])

  if (loading) return <LoadingSkeleton rows={4} />
  if (error) return <ErrorBanner message={error} />

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Usage and activity metrics for your authorized scope."
      />

      {isSuperAdmin(user) && superDash && (
        <>
          <ScopeBanner text="Organization-wide analytics" />
          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Total documents" value={superDash.documents} />
            <KpiCard label="Total queries" value={superDash.queries} />
            {Object.entries(superDash.users_by_role).map(([role, count]) => (
              <KpiCard key={role} label={`${role.replace('_', ' ')} users`} value={count} />
            ))}
          </div>

          {departments.length > 0 && (
            <div className="mb-4">
              <select
                value={selectedDept}
                onChange={(e) => setSelectedDept(e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {departments.map((d) => (
                  <option key={d.department_id} value={d.department_id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </>
      )}

      {deptDash && (
        <>
          {!isSuperAdmin(user) && (
            <ScopeBanner text={`Department: ${selectedDept}`} />
          )}
          <div className="grid gap-4 sm:grid-cols-3">
            <KpiCard label="Users" value={deptDash.users} />
            <KpiCard label="Documents" value={deptDash.documents} />
            <KpiCard label="Queries" value={deptDash.queries} />
          </div>
        </>
      )}
    </div>
  )
}
