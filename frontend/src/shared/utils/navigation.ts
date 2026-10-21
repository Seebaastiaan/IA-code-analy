type Navigate = (to: string) => void

let navigate: Navigate = (to) => window.location.assign(to)

/** La app registra aquí el navegador del router (para usarlo fuera de componentes, p. ej. en toasts). */
export const setNavigator = (fn: Navigate) => {
  navigate = fn
}

export const navigateTo = (to: string) => navigate(to)
