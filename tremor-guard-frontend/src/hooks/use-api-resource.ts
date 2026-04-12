import { useEffect, useRef, useState } from 'react'

interface AsyncState<T> {
  data: T | null
  error: string | null
  isLoading: boolean
}

export function useApiResource<T>(loader: () => Promise<T>, deps: unknown[] = []) {
  const loaderRef = useRef(loader)
  const depsKey = JSON.stringify(deps)
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    isLoading: true,
  })
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    loaderRef.current = loader
  }, [loader])

  useEffect(() => {
    let cancelled = false

    loaderRef.current()
      .then((data) => {
        if (!cancelled) {
          setState({ data, error: null, isLoading: false })
        }
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setState({ data: null, error: error.message, isLoading: false })
        }
      })

    return () => {
      cancelled = true
    }
  }, [depsKey, reloadKey])

  return {
    ...state,
    reload: () => {
      setState((current) => ({ ...current, isLoading: true, error: null }))
      setReloadKey((value) => value + 1)
    },
  }
}
