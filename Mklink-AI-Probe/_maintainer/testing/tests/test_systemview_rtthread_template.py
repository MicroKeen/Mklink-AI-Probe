"""Compile and execute the shipped adapter against RT-Thread ABI variants."""
from pathlib import Path
import shutil
import subprocess

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "mklink/systemview_sources/SEGGER_SYSVIEW_RTThread.c"


@pytest.mark.parametrize("layout,hooklist,name_size", [
    (40, 0, 8), (41, 0, 8), (50, 0, 8), (51, 0, 8), (51, 1, 8),
    (50, 0, 0), (51, 1, 0),
])
def test_rtthread_adapter_task_info_and_hooks(tmp_path, layout, hooklist, name_size):
    cc = shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("C compiler is required for the target adapter regression")
    shutil.copyfile(SOURCE, tmp_path / SOURCE.name)
    (tmp_path / "rtthread.h").write_text(r'''
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#define RT_USING_HOOK
#define RT_HOOK_USING_FUNC_PTR
#define RT_TICK_PER_SECOND 1000
#if LAYOUT == 51
#define RT_VERSION_MAJOR 5
#define RT_VERSION_MINOR 1
#else
#define RT_VERSION (LAYOUT / 10)
#define RT_SUBVERSION (LAYOUT % 10)
#endif
#if HOOKLIST
#define RT_USING_HOOKLIST
#endif
#define RT_Object_Class_Thread 1
typedef struct rt_list_node { struct rt_list_node *next, *prev; } rt_list_t;
#if RT_NAME_MAX > 0
#define OBJECT_NAME char name[RT_NAME_MAX]
#else
#define OBJECT_NAME const char *name
#endif
#define OBJECT_FIELDS OBJECT_NAME; unsigned char type, flags; rt_list_t list
struct rt_object { OBJECT_FIELDS; };
struct rt_thread {
#if LAYOUT >= 50
    struct rt_object parent;
#else
    OBJECT_FIELDS;
#endif
#if LAYOUT == 51
    struct { unsigned current_priority; } scheduler;
#define RT_SCHED_PRIV(t) ((t)->scheduler)
#else
    unsigned current_priority;
#endif
    void *stack_addr;
    unsigned stack_size;
};
typedef struct rt_thread *rt_thread_t;
typedef void *rt_timer_t;
struct rt_object_information { rt_list_t object_list; };
static struct rt_object_information objects;
static struct rt_thread idle_thread;
static unsigned critical_depth, create_hooks, scheduler_hooks;
static void (*scheduler_callback)(rt_thread_t, rt_thread_t);
static void (*create_callback)(rt_thread_t);
static void rt_enter_critical(void) { ++critical_depth; }
static void rt_exit_critical(void) { assert(critical_depth); --critical_depth; }
static unsigned rt_tick_get(void) { return 123; }
static rt_thread_t rt_thread_idle_gethandler(void) { return &idle_thread; }
static struct rt_object_information *rt_object_get_information(unsigned type) {
    assert(type == RT_Object_Class_Thread); return &objects;
}
#define rt_list_entry(node, type, member) ((type *)((char *)(node) - offsetof(type, member)))
#define rt_memset memset
#define rt_memcpy memcpy
static void rt_kprintf(const char *format, ...) { (void)format; }
#define INIT_COMPONENT_EXPORT(fn)
static void rt_scheduler_sethook(void (*fn)(rt_thread_t, rt_thread_t)) {
    ++scheduler_hooks; scheduler_callback = fn;
}
#if HOOKLIST
struct rt_thread_inited_hooklistnode { void (*handler)(rt_thread_t); rt_list_t list_node; };
#define RT_OBJECT_HOOKLIST_DEFINE_NODE(hook, node, fn) \
    struct rt_thread_inited_hooklistnode node = { fn, {NULL, NULL} }
static void rt_thread_inited_sethook(struct rt_thread_inited_hooklistnode *node) {
    ++create_hooks; create_callback = node->handler;
}
#elif LAYOUT == 40
static void rt_thread_inited_sethook(void (*fn)(rt_thread_t)) {
    ++create_hooks; create_callback = fn;
}
#endif
''', encoding="utf-8")
    (tmp_path / "SEGGER_RTT.h").write_text("static unsigned _SEGGER_RTT;\n", encoding="utf-8")
    (tmp_path / "SEGGER_SYSVIEW.h").write_text(r'''
typedef uintptr_t U32;
typedef unsigned long long U64;
typedef struct { U32 TaskID; const char *sName; unsigned Prio; U32 StackBase; unsigned StackSize; } SEGGER_SYSVIEW_TASKINFO;
typedef struct { U64 (*pfGetTime)(void); void (*pfSendTaskList)(void); } SEGGER_SYSVIEW_OS_API;
static unsigned task_info_count, create_count, idle_count, exec_count, stop_count;
static char captured_names[8][65];
static U32 captured_ids[8];
static void SEGGER_SYSVIEW_SendTaskInfo(const SEGGER_SYSVIEW_TASKINFO *info) {
    assert(critical_depth && task_info_count < 8);
    assert(info->Prio == 7 && info->StackSize == 1024);
    assert(info->StackBase == 0x20001000);
    assert(strlen(info->sName) <= 32);
    strcpy(captured_names[task_info_count], info->sName);
    captured_ids[task_info_count++] = info->TaskID;
}
static void SEGGER_SYSVIEW_OnTaskStopExec(void) { ++stop_count; }
static void SEGGER_SYSVIEW_OnTaskStartExec(U32 id) { assert(id); ++exec_count; }
static void SEGGER_SYSVIEW_OnIdle(void) { ++idle_count; }
static void SEGGER_SYSVIEW_OnTaskCreate(U32 id) { assert(id); ++create_count; }
static void SEGGER_SYSVIEW_Conf(void) {}
static void SEGGER_SYSVIEW_Start(void) {}
extern const SEGGER_SYSVIEW_OS_API SYSVIEW_X_OS_TraceAPI;
static void SEGGER_SYSVIEW_SendTaskList(void) { SYSVIEW_X_OS_TraceAPI.pfSendTaskList(); }
''', encoding="utf-8")
    (tmp_path / "exercise.c").write_text(r'''
#include "SEGGER_SYSVIEW_RTThread.c"
static void initialize_thread(struct rt_thread *thread, const char *name, size_t length) {
    struct rt_object *object = (struct rt_object *)thread;
    memset(thread, 0xa5, sizeof(*thread));
#if RT_NAME_MAX > 0
    memset(object->name, 0, RT_NAME_MAX);
    memcpy(object->name, name, length);
#else
    (void)length;
    object->name = name;
#endif
#if LAYOUT == 51
    RT_SCHED_PRIV(thread).current_priority = 7;
#else
    thread->current_priority = 7;
#endif
    thread->stack_addr = (void *)0x20001000;
    thread->stack_size = 1024;
}
int main(void) {
    struct rt_thread full, short_name;
    rt_list_t *head = &objects.object_list;
    rt_list_t *first = &((struct rt_object *)&full)->list;
    rt_list_t *second = &((struct rt_object *)&short_name)->list;
    rt_list_t *idle = &((struct rt_object *)&idle_thread)->list;
    initialize_thread(&full, "12345678", 8);
    initialize_thread(&short_name, "worker", 6);
    initialize_thread(&idle_thread, "idle", 4);
    head->next=first; first->next=second; second->next=idle; idle->next=head;
    assert(rt_trace_init() == 0);
    assert(critical_depth == 0 && scheduler_hooks == 1);
    assert(task_info_count == 2);
    assert(!strcmp(captured_names[0], "12345678"));
    assert(!strcmp(captured_names[1], "worker"));
    assert(captured_ids[0] == (U32)&full && captured_ids[1] == (U32)&short_name);
    assert(create_hooks == (HOOKLIST || LAYOUT == 40));
    if (create_callback) { create_callback(&full); assert(create_count == 1); }
    scheduler_callback(&full, &idle_thread);
    assert(idle_count == 1 && exec_count == 1 && stop_count == 1);
    return 0;
}
''', encoding="utf-8")
    executable = tmp_path / "exercise.exe"
    command = [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
               "-DUSE_SYSTEMVIEW", f"-DLAYOUT={layout}", f"-DHOOKLIST={hooklist}",
               f"-DRT_NAME_MAX={name_size}", str(tmp_path / "exercise.c"), "-o", str(executable)]
    built = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(executable)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert ran.returncode == 0, ran.stdout + ran.stderr
