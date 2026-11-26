import { Button, Icon, Modal, Spinner } from '@/shared/ui'
import { useRemoveRepo } from '../hooks/useRemoveRepo'
import type { Repo } from '../types'

/** Confirmación antes de eliminar un repositorio: borra sus análisis y reglas, no el repositorio de GitHub. */
export function DeleteRepoDialog({ repo, onClose }: { repo: Repo; onClose: () => void }) {
  const remove = useRemoveRepo(onClose)
  return (
    <Modal onClose={onClose} className="max-w-md">
      <div className="p-5 sm:p-6">
        <h2 className="font-semibold">¿Eliminar {repo.name}?</h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          Se borran todos sus análisis, hallazgos, reglas de negocio cargadas, pruebas generadas y enlaces para compartir. No se puede deshacer.
        </p>
        <p className="mt-2 text-sm text-slate-500">El repositorio en GitHub no se toca: puedes volver a analizarlo cuando quieras.</p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={remove.isPending}>
            Cancelar
          </Button>
          <Button onClick={() => remove.mutate(repo)} disabled={remove.isPending} className="bg-rose-600 hover:bg-rose-700 active:bg-rose-800 shadow-rose-600/25">
            {remove.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="trash" className="w-4 h-4" />}
            Eliminar
          </Button>
        </div>
      </div>
    </Modal>
  )
}
