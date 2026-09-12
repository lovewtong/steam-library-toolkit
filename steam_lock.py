"""OS-owned nonblocking locks; released by the OS even when a collector crashes."""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError("OUTPUT_BUSY：已有采集进程使用这个输出，请等待它结束或选择其他 -o") from None
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise RuntimeError("OUTPUT_BUSY：已有采集进程使用这个输出，请等待它结束或选择其他 -o") from None
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()
        # Keep the inode/path: unlinking would allow a new process to lock a different file.


@contextmanager
def collection_lock(output, extra_paths=()):
    target = Path(output).resolve()
    paths = {target.with_suffix(".collect.lock"), target.with_suffix(".candidates.collect.lock")}
    paths.update(Path(p).resolve().with_suffix(".collect.lock") for p in extra_paths)
    with ExitStack() as stack:
        for path in sorted(paths):
            stack.enter_context(file_lock(path))
        yield
