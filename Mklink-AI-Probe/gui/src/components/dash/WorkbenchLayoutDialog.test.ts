import { mount, flushPromises } from '@vue/test-utils';
import { expect, it, vi } from 'vitest';
import WorkbenchLayoutDialog from './WorkbenchLayoutDialog.vue';

const entry = { name: '已存布局', revision: 3, updated_at: 1, panel_count: 2 };
function setup() {
  const search = vi.fn(async (_query: string, scope: string) => ({ layouts: [entry], location: scope + '/frontend_layouts.json' }));
  const save = vi.fn(async () => ({})), load = vi.fn(async () => ({}));
  const wrapper = mount(WorkbenchLayoutDialog, { props: { mode: 'save', search, save, load }, global: { stubs: { WorkbenchSettingsDialog: { template: '<div><slot /></div>' } } } });
  return { wrapper, search, save, load };
}

it.each(['save', 'load'] as const)('clears an earlier selection when a new %s search finds nothing', async mode => {
  const { wrapper, search } = setup();
  await wrapper.setProps({ mode });
  await flushPromises();
  await wrapper.get('.layout-results button').trigger('click');
  search.mockResolvedValueOnce({ layouts: [], location: 'project/frontend_layouts.json' });
  await wrapper.get('.layout-search').trigger('submit');
  await flushPromises();
  expect(wrapper.get('.layout-submit button').attributes('disabled')).toBeDefined();
  wrapper.unmount();
});

it('defaults to project, requires selection before overwrite, and retains input after conflict', async () => {
  const { wrapper, search, save } = setup();
  await flushPromises();
  expect(search).toHaveBeenCalledWith('', 'project');
  await wrapper.get('.layout-results button').trigger('click');
  save.mockRejectedValueOnce(new Error('Saved layout changed'));
  await wrapper.get('.layout-submit').trigger('submit');
  await flushPromises();
  expect(save).toHaveBeenLastCalledWith(entry.name, 3, 'project');
  expect(wrapper.get('[role=alert]').text()).toContain('changed');
  expect(wrapper.emitted('close')).toBeUndefined();
  await wrapper.get('.layout-submit input').setValue('新布局');
  await wrapper.get('.layout-submit').trigger('submit');
  await flushPromises();
  expect(save).toHaveBeenLastCalledWith('新布局', 0, 'project');
  expect(wrapper.emitted('close')).toHaveLength(1);
  wrapper.unmount();
});

it('clears the selected revision when switching scope and searches within that scope', async () => {
  const { wrapper, search, save } = setup();
  await flushPromises();
  await wrapper.get('.layout-results button').trigger('click');
  await wrapper.get('select').setValue('global');
  await flushPromises();
  expect(search).toHaveBeenLastCalledWith('', 'global');
  expect((wrapper.get('.layout-submit input').element as HTMLInputElement).value).toBe('');
  await wrapper.get('.layout-search input').setValue('Motor');
  await wrapper.get('.layout-search').trigger('submit');
  await flushPromises();
  expect(search).toHaveBeenLastCalledWith('Motor', 'global');
  await wrapper.get('.layout-submit input').setValue('Global');
  await wrapper.get('.layout-submit').trigger('submit');
  await flushPromises();
  expect(save).toHaveBeenLastCalledWith('Global', 0, 'global');
  wrapper.unmount();
});

it('cancels without saving or loading and does not allow overwriting built-in templates', async () => {
  const { wrapper, search, save, load } = setup();
  search.mockResolvedValueOnce({ layouts: [{ ...entry, builtin: true } as typeof entry], location: 'global' });
  await flushPromises();
  await wrapper.get('select').setValue('global');
  await flushPromises();
  expect(wrapper.get('.layout-results button').attributes('disabled')).toBeDefined();
  await wrapper.get('.layout-buttons button[type=button]').trigger('click');
  expect(wrapper.emitted('close')).toHaveLength(1);
  expect(save).not.toHaveBeenCalled(); expect(load).not.toHaveBeenCalled();
  wrapper.unmount();
});
