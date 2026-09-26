# -*- coding: utf-8 -*-
"""LaMa 去水印(自包含,不依赖 simple-lama-inpainting / torch.hub)。

原理(读自 simple-lama-inpainting 0.1.2 源码):
    big-lama.pt 是 **TorchScript** 模型,torch.jit.load 直接吃。
    模型只吃 numpy/float 数组,跟 Pillow 版本无关 —— 所以本机
    Pillow 12 / 桌宠完全不受影响,也不会引入 pillow<10 的依赖冲突。

用法:
    python dewatermark.py <输入图> <输出图> [--mask x0,y0,x1,y1] [--grow N]

无 --mask 时用内置默认遮罩(右下角"贴+DeepSeek吧"水印,按 1672x941 参考)。
遮罩坐标按图片实际尺寸等比缩放。
"""
import argparse
import os

# 模型下载到 D 盘(东家偏好:别占 C 盘)。
os.environ.setdefault("TORCH_HOME", r"D:\torch-cache")

import numpy as np
import cv2
from PIL import Image
import torch
from torch.hub import download_url_to_file, get_dir

MODEL_URL = ("https://github.com/enesmsahin/simple-lama-inpainting/"
             "releases/download/v0.1.0/big-lama.pt")


def _model_path():
    """返回 TorchScript 权重路径,不存在则下载。"""
    model_dir = os.path.join(get_dir(), "checkpoints")
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(model_dir, "big-lama.pt")
    if not os.path.exists(path):
        print("[dewatermark] 下载模型 -> %s" % path)
        download_url_to_file(MODEL_URL, path, hash_prefix=None, progress=True)
    return path


def _load_model(device="cpu"):
    path = _model_path()
    print("[dewatermark] torch.jit.load(%s)" % path)
    m = torch.jit.load(path, map_location=device)
    m.eval()
    return m.to(device), device


def _scale_mask(box, W, H, ref=(1672, 941)):
    x0, y0, x1, y1 = box
    sx, sy = W / ref[0], H / ref[1]
    return (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))


def _to_tensor(arr_bhwc):
    """HWC uint8 -> CHW float32 [0,1]"""
    t = np.transpose(arr_bhwc.astype(np.float32) / 255.0, (2, 0, 1))
    return torch.from_numpy(t)[None]


def dewatermark(src, dst, mask_box, grow=0, device="cpu"):
    im = Image.open(src).convert("RGB")
    W, H = im.size
    x0, y0, x1, y1 = _scale_mask(mask_box, W, H)
    if grow:
        x0, y0 = max(0, x0 - grow), max(0, y0 - grow)
        x1, y1 = min(W, x1 + grow), min(H, y1 + grow)

    img = np.array(im)                      # HWC uint8
    mask = np.zeros((H, W), dtype=np.uint8)
    mask[y0:y1, x0:x1] = 255

    # LaMa 要求 (H,W) 是 8 的倍数 -> 对称补边,输出再裁回
    def ceil8(v):
        return v if v % 8 == 0 else (v // 8 + 1) * 8

    pH, pW = ceil8(H), ceil8(W)
    img_p = np.pad(img, ((0, pH - H), (0, pW - W), (0, 0)), mode="symmetric")
    # 遮罩也用对称补,且保持 0/255
    mask_p = np.pad(mask, ((0, pH - H), (0, pW - W)), mode="symmetric")

    print("[dewatermark] 原图 %dx%d,遮罩 %s" % (W, H, (x0, y0, x1, y1)))
    model, dev = _load_model(device)

    t_img = _to_tensor(img_p).to(dev)
    t_mask = (torch.from_numpy(mask_p.astype(np.float32) / 255.0)[None][None] > 0).float().to(dev)

    with torch.inference_mode():
        out = model(t_img, t_mask)

    res = out[0].permute(1, 2, 0).detach().cpu().numpy()
    res = np.clip(res * 255, 0, 255).astype(np.uint8)
    res = res[:H, :W]

    # 只替换遮罩区,其余像素原样保留
    final = img.copy()
    final[y0:y1, x0:x1] = res[y0:y1, x0:x1]

    Image.fromarray(final).save(dst, quality=97)
    print("[dewatermark] 已保存 -> %s" % dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--mask", default="980,820,1672,920",
                    help="x0,y0,x1,y1 (按 1672x941 参考比例缩放)")
    ap.add_argument("--grow", type=int, default=0)
    a = ap.parse_args()
    box = tuple(int(v) for v in a.mask.split(","))
    dewatermark(a.src, a.dst, box, grow=a.grow)


if __name__ == "__main__":
    main()
