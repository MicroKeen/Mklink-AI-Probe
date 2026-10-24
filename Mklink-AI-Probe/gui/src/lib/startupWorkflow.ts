export type StartupStep = 'backend' | 'modules' | 'workspace'
export type StepState = 'pending' | 'active' | 'done' | 'failed'

export async function startWorkspace<T>(options: {
  backend: () => Promise<void>
  load: () => Promise<T>
  mount: (loaded: T) => Promise<void>
  step: (step: StartupStep, state: StepState) => void
  backendFailed: (error: unknown) => void
}) {
  options.step('backend', 'active')
  options.step('modules', 'active')
  // Load code while the independent backend starts. Mount only after endpoint
  // initialization settles, so setup hooks never capture a provisional URL.
  const backend = options.backend().then(
    () => options.step('backend', 'done'),
    error => { options.step('backend', 'failed'); options.backendFailed(error) },
  )
  const modules = options.load().then(loaded => {
    options.step('modules', 'done')
    return loaded
  }, error => { options.step('modules', 'failed'); throw error })
  const [, loaded] = await Promise.all([backend, modules])
  options.step('workspace', 'active')
  try {
    await options.mount(loaded)
    options.step('workspace', 'done')
  } catch (error) {
    options.step('workspace', 'failed')
    throw error
  }
}
