"""BaseConfigPopup and ConfigPopup (engine + model configuration).

Phase 140 P2-1: Extracted from katrain/gui/popups.py.
"""
from __future__ import annotations

import glob
import json
import os
import re
import stat
import threading
import time
from typing import Any
from zipfile import ZipFile

import urllib3
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivy.utils import platform
from kivymd.app import MDApp

from katrain.common.humanlike_config import normalize_humanlike_config
from katrain.common.model_labels import classify_model_strength, get_model_basename
from katrain.common.resource_utils import get_package_path
from katrain.core.constants import (
    DATA_FOLDER,
    OUTPUT_DEBUG,
    OUTPUT_ERROR,
    OUTPUT_INFO,
    STATUS_INFO,
)
from katrain.core.engine import KataGoEngine
from katrain.core.lang import i18n
from katrain.gui.popups.quick_config import QuickConfigGui
from katrain.gui.theme import Theme
from katrain.gui.widgets.factory import Label
from katrain.gui.widgets.progress_loader import ProgressLoader


class BaseConfigPopup(QuickConfigGui):
    MODEL_ENDPOINTS: dict[str, str] = {
        "Latest distributed model": "https://katagotraining.org/api/networks/newest_training/",
        "Strongest distributed model": "https://katagotraining.org/api/networks/get_strongest/",
    }
    MODELS: dict[str, str] = {
        "old 15 block model": "https://github.com/lightvector/KataGo/releases/download/v1.3.2/g170e-b15c192-s1672170752-d466197061.txt.gz",
        "Human-like model": "https://github.com/lightvector/KataGo/releases/download/v1.15.0/b18c384nbt-humanv0.bin.gz",
    }
    MODEL_DESC: dict[str, str] = {
        "Fat 40 block model": "https://d3dndmfyhecmj0.cloudfront.net/g170/neuralnets/g170e-b40c384x2-s2348692992-d1229892979.zip",
        "Recommended 18b model": "https://media.katagotraining.org/uploaded/networks/models/kata1/kata1-b18c384nbt-s9996604416-d4316597426.bin.gz",
        "old 20 block model": "https://github.com/lightvector/KataGo/releases/download/v1.4.5/g170e-b20c256x2-s5303129600-d1228401921.bin.gz",
        "old 30 block model": "https://github.com/lightvector/KataGo/releases/download/v1.4.5/g170-b30c320x2-s4824661760-d1229536699.bin.gz",
        "old 40 block model": "https://github.com/lightvector/KataGo/releases/download/v1.4.5/g170-b40c256x2-s5095420928-d1229425124.bin.gz",
    }

    KATAGOS: dict[str, dict[str, str]] = {
        "win": {
            "OpenCL v1.16.0": "https://github.com/lightvector/KataGo/releases/download/v1.16.0/katago-v1.16.0-opencl-windows-x64.zip",
            "Eigen AVX2 (Modern CPUs) v1.16.0": "https://github.com/lightvector/KataGo/releases/download/v1.16.0/katago-v1.16.0-eigenavx2-windows-x64.zip",
            "Eigen (CPU, Non-optimized) v1.16.0": "https://github.com/lightvector/KataGo/releases/download/v1.16.0/katago-v1.16.0-eigen-windows-x64.zip",
            "OpenCL v1.16.0 (bigger boards)": "https://github.com/lightvector/KataGo/releases/download/v1.16.0/katago-v1.16.0-opencl-windows-x64+bs50.zip",
        },
        "linux": {
            "OpenCL v1.16.0": "https://github.com/lightvector/KataGo/releases/download/v1.16.0/katago-v1.16.0-opencl-linux-x64.zip",
            "Eigen AVX2 (Modern CPUs) v1.16.0": "https://github.com/lightvector/KataGo/releases/download/v1.16.0/katago-v1.16.0-eigenavx2-linux-x64.zip",
            "Eigen (CPU, Non-optimized) v1.16.0": "https://github.com/lightvector/KataGo/releases/download/v1.16.0/katago-v1.16.0-eigen-linux-x64.zip",
            "OpenCL v1.16.0 (bigger boards)": "https://github.com/lightvector/KataGo/releases/download/v1.16.0/katago-v1.16.0-opencl-linux-x64+bs50.zip",
        },
        "just-descriptions": {},
    }

    def __init__(self, katrain: Any) -> None:
        super().__init__(katrain)
        self.paths = [
            self.katrain.config("engine/model"),
            self.katrain.config("engine/humanlike_model"),
            "katrain/models",
            DATA_FOLDER,
        ]
        self.katago_paths = [self.katrain.config("engine/katago"), DATA_FOLDER]
        self.last_clicked_download_models = 0.0

    def check_models(self, *args: Any) -> None:
        all_models = [self.MODELS, self.MODEL_DESC, self.katrain.config("dist_models", {})]

        def extract_model_file(model: str) -> str | None:
            try:
                match = re.match(r".*/([^/]+)", model)
                if match:
                    return match[1].replace(".zip", ".bin.gz")
                return None
            except (TypeError, IndexError):
                return None

        def find_description(path: str) -> str:
            file = os.path.split(path)[1]
            file_to_desc = {extract_model_file(model): desc for mods in all_models for desc, model in mods.items()}
            if file in file_to_desc:
                return f"{file_to_desc[file]}  -  {path}"
            else:
                return path

        done: set[str] = set()
        model_files: list[str] = []
        humanlike_model_files: list[str] = []
        distributed_training_models = os.path.expanduser(os.path.join(DATA_FOLDER, "katago_contribute/kata1/models"))
        for path in self.paths + [self.model_path.text, self.humanlike_model_path.text, distributed_training_models]:
            path = (path or "").rstrip("/\\")
            if path.startswith("katrain"):
                path = path.replace("katrain", get_package_path().rstrip("/\\"), 1)
            path = os.path.expanduser(path)
            if not os.path.isdir(path):
                path, _file = os.path.split(path)
            slashpath = path.replace("\\", "/")
            if slashpath in done or not os.path.isdir(path):
                continue
            done.add(slashpath)
            files = [
                f.replace("/", os.path.sep).replace(get_package_path(), "katrain")
                for ftype in ["*.bin.gz", "*.txt.gz"]
                for f in glob.glob(slashpath + "/" + ftype)
                if ".tmp." not in f
            ]
            if files and path not in self.paths:
                self.paths.append(path)  # persistent on paths with models found
            model_files += files
            for file in files:
                if "human" in file:
                    humanlike_model_files.append(file)

        # no description to bottom
        model_files_with_desc: list[tuple[str, str]] = sorted(
            [(find_description(path), path) for path in model_files],
            key=lambda descpath: ("Recommended" not in descpath[0], "  -  " not in descpath[0], descpath[0]),
        )
        models_available_msg = i18n._("models available").format(num=len(model_files_with_desc))
        self.model_files.values = [models_available_msg] + [desc for desc, path in model_files_with_desc]
        self.model_files.value_keys = [""] + [path for desc, path in model_files_with_desc]
        self.model_files.text = models_available_msg

        humanlike_model_files_with_desc: list[tuple[str, str]] = sorted(
            [(find_description(path), path) for path in humanlike_model_files],
            key=lambda descpath: ("Recommended" not in descpath[0], "  -  " not in descpath[0], descpath[0]),
        )
        humanlike_models_available_msg = i18n._("models available").format(num=len(humanlike_model_files_with_desc))
        self.humanlike_model_files.values = [humanlike_models_available_msg] + [
            desc for desc, path in humanlike_model_files_with_desc
        ]
        self.humanlike_model_files.value_keys = [""] + [path for desc, path in humanlike_model_files_with_desc]
        self.humanlike_model_files.text = humanlike_models_available_msg

    def check_katas(self, *args: Any) -> None:
        def find_description(path: str) -> str:
            file = os.path.split(path)[1].replace(".exe", "")
            file_to_desc = {}
            for _, kgs in self.KATAGOS.items():
                for desc, kg in kgs.items():
                    match = re.match(r".*/([^/]+)", kg)
                    if match:
                        file_to_desc[match[1].replace(".zip", "")] = desc
            if file in file_to_desc:
                return f"{file_to_desc[file]}  -  {path}"
            else:
                return path

        done = set()
        kata_files = []
        for path in self.katago_paths + [self.katago_path.text]:
            path = path.rstrip("/\\")
            if path.startswith("katrain"):
                path = path.replace("katrain", get_package_path().rstrip("/\\"), 1)
            path = os.path.expanduser(path)
            if not os.path.isdir(path):
                path, _file = os.path.split(path)
            slashpath = path.replace("\\", "/")
            if slashpath in done or not os.path.isdir(path):
                continue
            done.add(slashpath)
            files = [
                f.replace("/", os.path.sep).replace(get_package_path(), "katrain")
                for ftype in ["katago*"]
                for f in glob.glob(slashpath + "/" + ftype)
                if os.path.isfile(f) and not f.endswith(".zip")
            ]
            if files and path not in self.paths:
                self.paths.append(path)  # persistent on paths with models found
            kata_files += files

        kata_files = sorted(
            [(path, find_description(path)) for path in kata_files],
            key=lambda f: ("bs29" in f[0]) * 0.1 - (f[0] != f[1]),
        )
        katas_available_msg = i18n._("katago binaries available").format(num=len(kata_files))
        self.katago_files.values = [katas_available_msg, i18n._("default katago option")] + [
            desc for path, desc in kata_files
        ]
        self.katago_files.value_keys = ["", ""] + [path for path, desc in kata_files]
        self.katago_files.text = katas_available_msg

    def download_models(self, *_largs: Any) -> None:
        if time.time() - self.last_clicked_download_models > 5:
            self.last_clicked_download_models = time.time()
            threading.Thread(target=self._download_models, daemon=True).start()

    def _download_models(self) -> None:
        def download_complete(req: Any, tmp_path: str, path: str, model: str) -> None:
            try:
                os.rename(tmp_path, path)
                self.katrain.log(f"Download of {model} complete -> {path}", OUTPUT_INFO)
            except Exception as e:
                self.katrain.log(f"Download of {model} complete, but could not move file: {e}", OUTPUT_ERROR)
            self.check_models()

        for c in self.download_progress_box.children:
            if isinstance(c, ProgressLoader) and c.request:
                c.request.cancel()
        Clock.schedule_once(lambda _dt: self.download_progress_box.clear_widgets(), -1)  # main thread
        downloading = False

        dist_models = {k: v for k, v in self.katrain.config("dist_models", {}).items() if k in self.MODEL_ENDPOINTS}

        for name, url in self.MODEL_ENDPOINTS.items():
            try:
                http = urllib3.PoolManager()
                response = http.request("GET", url)
                if response.status != 200:
                    raise Exception(
                        f"Request to {url} returned code {response.status} != 200: {response.data.decode()}"
                    )
                dist_models[name] = json.loads(response.data.decode("utf-8"))["model_file"]
            except Exception as e:
                self.katrain.log(f"Failed to retrieve info for model: {e}", OUTPUT_INFO)
        self.katrain.set_config_section("dist_models", dict(dist_models))
        self.katrain.save_config(key="dist_models")

        for name, url in {**self.MODELS, **dist_models}.items():
            filename = os.path.split(url)[1]
            if not any(
                os.path.split(f)[1] == filename for f in self.model_files.values + self.humanlike_model_files.values
            ):
                savepath = os.path.expanduser(os.path.join(DATA_FOLDER, filename))
                savepath_tmp = savepath + ".part"
                self.katrain.log(f"Downloading {name} from {url} to {savepath_tmp}", OUTPUT_INFO)
                Clock.schedule_once(
                    lambda _dt, _savepath=savepath, _savepath_tmp=savepath_tmp, _url=url, _name=name: ProgressLoader(
                        self.download_progress_box,
                        download_url=_url,
                        path_to_file=_savepath_tmp,
                        downloading_text=f"Downloading {_name}: " + "{}",
                        label_downloading_text=f"Starting download for {_name}",
                        download_complete=lambda req, tmp=_savepath_tmp, path=_savepath, model=_name: download_complete(
                            req, tmp, path, model
                        ),
                        download_redirected=lambda req, mname=_name: self.katrain.log(
                            f"Download {mname} redirected {req.resp_headers}", OUTPUT_DEBUG
                        ),
                        download_error=lambda req, error, mname=_name: self.katrain.log(
                            f"Download of {mname} failed or cancelled ({error})", OUTPUT_ERROR
                        ),
                    ),
                    0,
                )  # main thread
                downloading = True
        if not downloading:
            Clock.schedule_once(
                lambda _dt: self.download_progress_box.add_widget(
                    Label(text=i18n._("All models downloaded"), font_name=i18n.font_name, text_size=(None, dp(50)))
                ),
                0,
            )  # main thread

    def download_katas(self, *_largs: Any) -> None:
        def unzipped_name(zipfile: str) -> str:
            if platform == "win":
                return zipfile.replace(".zip", ".exe")
            else:
                return zipfile.replace(".zip", "")

        def download_complete(req: Any, tmp_path: str, path: str, binary: str) -> None:
            try:
                if tmp_path.endswith(".zip"):
                    with ZipFile(tmp_path, "r") as zipObj:
                        exes = [f for f in zipObj.namelist() if f.startswith("katago")]
                        if len(exes) != 1:
                            raise FileNotFoundError(
                                f"Zip file {tmp_path} does not contain exactly 1 file starting with 'katago' (contents: {zipObj.namelist()})"
                            )
                        with open(path, "wb") as fout:
                            fout.write(zipObj.read(exes[0]))
                            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP)
                        for f in zipObj.namelist():
                            if f.lower().endswith("dll"):
                                try:
                                    with open(os.path.join(os.path.split(path)[0], f), "wb") as fout:
                                        fout.write(zipObj.read(f))
                                except Exception:
                                    # Control-flow: file already exists or write failed, skip
                                    pass
                    os.remove(tmp_path)
                else:
                    os.rename(tmp_path, path)
                self.katrain.log(f"Download of katago binary {binary} complete -> {path}", OUTPUT_INFO)
            except Exception as e:
                self.katrain.log(
                    f"Download of katago binary {binary} complete, but could not move file: {e}", OUTPUT_ERROR
                )
            self.check_katas()

        for c in self.katago_download_progress_box.children:
            if isinstance(c, ProgressLoader) and c.request:
                c.request.cancel()
        self.katago_download_progress_box.clear_widgets()
        downloading = False
        for name, url in self.KATAGOS.get(platform, {}).items():
            filename = os.path.split(url)[1]
            exe_name = unzipped_name(filename)
            if not any(os.path.split(f)[1] == exe_name for f in self.katago_files.values):
                savepath_tmp = os.path.expanduser(os.path.join(DATA_FOLDER, filename))
                exe_path_name = os.path.expanduser(os.path.join(DATA_FOLDER, exe_name))
                self.katrain.log(f"Downloading binary {name} from {url} to {savepath_tmp}", OUTPUT_INFO)
                ProgressLoader(
                    root_instance=self.katago_download_progress_box,
                    download_url=url,
                    path_to_file=savepath_tmp,
                    downloading_text=f"Downloading {name}: " + "{}",
                    label_downloading_text=f"Starting download for {name}",
                    download_complete=lambda req, tmp=savepath_tmp, path=exe_path_name, model=name: download_complete(
                        req, tmp, path, model
                    ),
                    download_redirected=lambda req, mname=name: self.katrain.log(
                        f"Download {mname} redirected {req.resp_headers}", OUTPUT_DEBUG
                    ),
                    download_error=lambda req, error, mname=name: self.katrain.log(
                        f"Download of {mname} failed or cancelled ({error})", OUTPUT_ERROR
                    ),
                )
                downloading = True
        if not downloading:
            if not self.KATAGOS.get(platform):
                self.katago_download_progress_box.add_widget(
                    Label(
                        text=f"No binaries available for platform {platform}",
                        text_size=(None, dp(50)),
                        font_name=Theme.DEFAULT_FONT,
                    )
                )
            else:
                self.katago_download_progress_box.add_widget(
                    Label(text=i18n._("All binaries downloaded"), font_name=i18n.font_name, text_size=(None, dp(50)))
                )


class ConfigPopup(BaseConfigPopup):
    # Phase 88: Settings mode and humanlike toggle
    current_mode = StringProperty("standard")  # "automatic", "standard", "advanced"

    def __init__(self, katrain: Any) -> None:
        super().__init__(katrain)
        Clock.schedule_once(self.check_katas)
        MDApp.get_running_app().bind(language=self.check_models)
        MDApp.get_running_app().bind(language=self.check_katas)

    def get_model_display_text(self, model_path: str) -> str:
        """Get localized display text for model.

        Handles empty path gracefully with model:none fallback.
        """
        if not model_path:
            return i18n._("model:none")

        category = classify_model_strength(model_path)
        if category == "unknown":
            basename = get_model_basename(model_path)
            if not basename:
                return i18n._("model:none")
            # Use placeholder form: "Other: {name}"
            return i18n._("model:unknown_with_name").format(name=basename)
        return i18n._(f"model:{category}")

    def update_config(self, save_to_file: bool = True, close_popup: bool = True) -> set[str]:
        # Phase 88: Normalize humanlike config before saving
        # Simplify: Treat non-empty path as enabled
        model_path = self.humanlike_model_path.text
        last_path = self.katrain.config("engine/humanlike_model_last", "")
        # Phase 140: use shared normalizer (single source of truth, tested in
        # tests/test_humanlike_config.py).
        model, last, effective_on = normalize_humanlike_config(
            bool(model_path),  # toggle_on: ON iff user picked a path
            model_path,
            last_path,
        )
        enabled = bool(model_path)
        # Update humanlike_model_path to normalized value before parent saves
        self.humanlike_model_path.text = model
        # Store last path in config (will be saved by parent)
        self.katrain.update_engine_config(humanlike_model_last=last)

        updated = super().update_config(save_to_file=save_to_file, close_popup=close_popup)
        self.katrain.debug_level = self.katrain.config("general/debug_level", OUTPUT_INFO)

        # Sync UI state to match persisted config
        if enabled and not effective_on:
            self.katrain.controls.set_status(i18n._("humanlike:forced_off"), STATUS_INFO)

        ignore = {
            "max_visits",
            "fast_visits",
            "max_time",
            "enable_ownership",
            "wide_root_noise",
            "humanlike_model_last",
        }
        detected_restart = [key for key in updated if "engine" in key and not any(ig in key for ig in ignore)]
        if detected_restart:

            def restart_engine(_dt: Any) -> None:
                self.katrain.controls.set_status("", STATUS_INFO)
                self.katrain.log(f"Restarting Engine after {detected_restart} settings change")
                self.katrain.controls.set_status(i18n._("restarting engine"), STATUS_INFO)

                old_engine = self.katrain.engine  # type: KataGoEngine
                old_proc = old_engine.katago_process
                if old_proc:
                    old_engine.shutdown(finish=False)
                new_engine = KataGoEngine(self.katrain, self.katrain.config("engine"))
                self.katrain.engine = new_engine
                self.katrain.game.engines = {"B": new_engine, "W": new_engine}
                self.katrain.game.analyze_all_nodes(
                    analyze_fast=True
                )  # old engine was possibly broken, so make sure we redo any failures
                self.katrain.update_state()

            Clock.schedule_once(restart_engine, 0)
        return updated
