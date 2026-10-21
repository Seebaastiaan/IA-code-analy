import { Link } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { buttonClass, EmptyState } from '@/shared/ui'

export default function NotFoundPage() {
  return (
    <div className="min-h-screen grid place-items-center p-6">
      <EmptyState icon="alert" title="Esta página no existe">
        <Link to={paths.dashboard()} className={buttonClass('primary', 'mt-3')}>
          Ir al tablero
        </Link>
      </EmptyState>
    </div>
  )
}
