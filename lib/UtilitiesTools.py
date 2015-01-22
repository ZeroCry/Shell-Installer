#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# Cinnamon Installer
#
# Authors: Lester Carballo Pérez <lestcape@gmail.com>
#
#
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation; either version 2 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
#  USA

from __future__ import print_function

import os, sys, tempfile, time, shutil, zipfile, tarfile
import SystemTools

try:
    import threading, Queue
    try:
        import urllib2
    except:
        import urllib.request as urllib2
except Exception:
    e = sys.exc_info()[1]
    print(str(e))
    #sys.exit(1)

ABORT_NONE = 0
ABORT_ERROR = 1
ABORT_USER = 2

EFECTIVE_USER = SystemTools.get_user()
EFECTIVE_IDS = [SystemTools.get_user_id(EFECTIVE_USER), SystemTools.get_group_id(EFECTIVE_USER)]
EFECTIVE_MODE = SystemTools.get_standar_mode()
HOME_PATH = SystemTools.get_home()

class ThreadPool():
    def __init__(self, max_process=1):
        self.max_process = max_process
        self.work_count = 0

    def get_max_process(self):
        return self.max_process

    def execute_task_async(self, task, works, on_finished=None):
        #Wont bocking the main thread.
        threading.Thread(target = self._execute_task_pool,
                         args=(task, works, on_finished))

    def execute_task(self, task, works, on_finished=None):
        self._execute_task_pool(task, works, on_finished)

    def _execute_task_pool(self, task, works, on_finished):
        if not callable(task):
            raise Exception(_("Invalid function to execute is passed as a parameter of the thread"))
        works_q = Queue.Queue()
        result_q = Queue.Queue()

        # Create the "thread pool"
        pool = [WorkerThread(task=task, works_q=works_q, result_q=result_q) for i in range(self.max_process)]

        # Start all threads
        for thread in pool:
            thread.start()

        # Give the workers some work to do
        self.work_count = 0
        for work in works:
            self.work_count += 1
            works_q.put((work, works[work]["params"]))

        # Ask threads to die and wait for them to do it
        for thread in pool:
            thread.join()

        # Now get all the results
        while not result_q.empty():
            # Blocking 'get' from a Queue.
            result = result_q.get()
            work = result[0]
            works[work]["result"] = result[1]
            works[work]["error"] = result[2]
            self.work_count -= 1

        if callable(on_finished):
            on_finished(works)

class WorkerThread(threading.Thread):
    ''' A worker thread that takes task functions and parameters
        from a queue, execute the function passing the parameters
        and reports the result.

        Input is done by placing task functions into the
        Queue passed in task_q.

        Output is done by placing the return of the task function
        (thats will be good to be a tuple), into the Queue passed
        in result_q.

        Ask the thread to stop by calling its join() method.
    '''
    def __init__(self, task, works_q, result_q):
        if not callable(task):
            raise Exception(_("Invalid function to execute is passed as a parameter of the thread"))
        super(WorkerThread, self).__init__()
        self.task = task
        self.works_q = works_q
        self.result_q = result_q
        self.stoprequest = threading.Event()

    def run(self):
        ''' As long as we weren't asked to stop, try to take new tasks from the
            queue. The tasks are taken with a blocking 'get', so no CPU
            cycles are wasted while waiting.
            Also, 'get' is given a timeout, so stoprequest is always checked,
            even if there's nothing in the queue.
        '''
        while (not self.stoprequest.isSet() or not self.works_q.empty()):
            try:
                work = self.works_q.get(True, 0.05) # Remove and return the task from the queue
                out = self.task(*work[1])
                self.result_q.put((work[0], out, None))
            except Queue.Empty:
                continue
            except Exception:
                e = sys.exc_info()[1]
                self.result_q.put((work[0], None, e))

    def join(self, timeout=None):
        self.stoprequest.set()
        super(WorkerThread, self).join(timeout)

class DownloadHelper():
    def __init__(self, max_process = 3):
        self.abort_download = ABORT_NONE
        self.pending_downloads = 0
        self.max_process = max_process

    def download_files(self, url_list, async=False, reporthook=None, user_params=None):
        self.abort_download = ABORT_NONE
        pool = ThreadPool(self.max_process)
        works = {}
        self.pending_downloads = len(url_list)
        for url in url_list:
           works[url] = {}
           works[url]["params"] = [url, url_list[url]["path"], reporthook, user_params]
           works[url]["result"] = None
           works[url]["error"] = None
        if async:
            pool.execute_task_async(self._download_file, works)
        else:
            pool.execute_task(self._download_file, works)
        return works

    def cancel_download(self):
        self.abort_download = ABORT_USER

    def is_download_cancelled(self):
        return self.abort_download == ABORT_USER

    def download_file(self, url, path=None, async=False, reporthook=None, user_params=None):
        self.abort_download = ABORT_NONE
        self.pending_downloads = 1
        outFile = self._download_file(url, path, reporthook, user_params)
        return outFile

    def _download_file(self, url, path=None, reporthook=None, user_params=None):
        if self.abort_download > ABORT_NONE:
            raise Exception(_("Download aborted."))
        fd, filename = tempfile.mkstemp()
        f = os.fdopen(fd, "wb")
        self._download_file_temp(url, f, filename, self.pending_downloads, reporthook, user_params)
        self.pending_downloads -= 1
        if path and os.path.isfile(filename):
            shutil.copyfile(filename, path)
            os.remove(filename)
            filename = path
        if os.path.isfile(filename):
            SystemTools.set_propietary_id(filename, EFECTIVE_IDS[0], EFECTIVE_IDS[1])
            SystemTools.set_mode(filename, EFECTIVE_MODE)
        return filename

    def _download_file_temp(self, url, outfd, outfile, pending_downloads, reporthook=None, user_params=None):
        try:
            self._url_retrieve(url, outfd, pending_downloads, reporthook, user_params)
        except KeyboardInterrupt:
            try:
                os.remove(outfile)
            except OSError:
                pass
            if self.abort_download == ABORT_ERROR:
                raise Exception(_("An error occurred while trying to access the server.  Please try again in a little while."))
            raise Exception(_("Download aborted."))

        return outfile

    def _reporthook(self, count, blockSize, totalSize, pending_downloads, user_params=None):
        pass
        '''
        if self.download_total_files > 1:
            fraction = (float(self.download_current_file) / float(self.download_total_files));
            self.progressbar.set_text("%s - %d / %d files" % (str(int(fraction*100)) + "%", self.download_current_file, self.download_total_files))
        else:
            fraction = count * blockSize / float((totalSize / blockSize + 1) *
                (blockSize))
            self.progressbar.set_text(str(int(fraction * 100)) + "%")

        if fraction > 0:
            self.progressbar.set_fraction(fraction)
        else:
            self.progress_bar_pulse()

       '''

    def _url_retrieve(self, url, f, pending_downloads, reporthook, user_param=None):        
        #Like the one in urllib. Unlike urllib.retrieve url_retrieve
        #can be interrupted. KeyboardInterrupt exception is rasied when
        #interrupted.
        count = 0
        block_size = 1024 * 8
        try:
            urlobj = urllib2.urlopen(url)
        except Exception:
            f.close()
            e = sys.exc_info()[1]
            print(str(e))
            self.abort_download = ABORT_ERROR
            raise KeyboardInterrupt
        total_size = int(urlobj.info()["content-length"])
        try:
            while self.abort_download == ABORT_NONE:
                data = urlobj.read(block_size)
                count += 1
                if not data:
                    break
                f.write(data)
                if (reporthook) and (callable(reporthook)):
                    if count*block_size > total_size:
                        reporthook(url, count, total_size/count, total_size, pending_downloads, user_param)
                    else:
                        reporthook(url, count, block_size, total_size, pending_downloads, user_param)
                else:
                    print(str(reporthook))
        except KeyboardInterrupt:
            self.abort_download = ABORT_USER
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))
            self.abort_download = ABORT_ERROR
        try:
            del urlobj
            f.close()
        except Exception:
            e = sys.exc_info()[1]
            print(str(e))

        if self.abort_download > ABORT_NONE:
            raise KeyboardInterrupt

class CompressorHelper():
    def __init__(self):
        self.collect_type = None
        self.last_comp = None

    def set_collection(self, collect_type):
        self.collect_type = collect_type

    def compress_folder(self, folder_path, file_path, type_compress):
        if type_compress == "tarfile":
            self._compress_folder_tar(folder_path, file_path)
        else:
            self._compress_folder_zip(folder_path, file_path)

    def extract_file(self, file_path, folder_path):
        if tarfile.is_tarfile(file_path):
            return self._extract_file_tar(file_path, folder_path)
        return self._extract_file_zip(file_path, folder_path)

    def get_members(self):
        if (self.last_comp) and (isinstance(self.last_comp, zipfile.ZipFile)):
            return self._get_zip_members(self.last_comp)
        else:
            return self._get_tar_members(self.last_comp)

    def _compress_folder_zip(self, folder_path, file_path):
        print("Not implemented")

    def _compress_folder_tar(self, folder_path, file_path):
        print("Not implemented")

    def _extract_file_zip(self, file_path, folder_path):
        self.last_comp = zipfile.ZipFile(file_path)
        if self.collect_type != "theme":
            zip_members = self._get_zip_members(self.last_comp)
        else:
            zip_members = None
        self.last_comp.extractall(folder_path, zip_members)

    def _extract_file_tar(self, file_path, folder_path):
        self.last_comp = tarfile.open(file_path)
        if self.collect_type != "theme":
            tar_members = self._get_tar_members(self.last_comp)
        else:
            tar_members = None
        self.last_comp.extractall(folder_path, tar_members)
        self.last_comp.close()

    def _get_tar_members(self, tar):
        parts = []
        for name in tar.getnames():
            if not name.endswith("/"):
                parts.append(name.split("/")[:-1])
        prefix = os.path.commonprefix(parts) or ""
        if prefix:
            prefix = "/".join(prefix) + "/"
        offset = len(prefix)
        for tarinfo in tar.getmembers():
            name = tarinfo.name
            if len(name) > offset:
                tarinfo.name = name[offset:]
                yield tarinfo

    def _get_zip_members(self, zip):
        parts = []
        for name in zip.namelist():
            if not name.endswith("/"):
                parts.append(name.split("/")[:-1])
        prefix = os.path.commonprefix(parts) or ""
        if prefix:
            prefix = "/".join(prefix) + "/"
        offset = len(prefix)
        for zipinfo in zip.infolist():
            name = zipinfo.filename
            if len(name) > offset:
                zipinfo.filename = name[offset:]
                yield zipinfo
