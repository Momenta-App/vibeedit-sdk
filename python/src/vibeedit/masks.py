from __future__ import annotations


def composite_with_mask(base, treatment, mask):
    import numpy

    background = numpy.asarray(base)
    foreground = numpy.asarray(treatment)
    matte = numpy.asarray(mask)
    if background.shape != foreground.shape:
        raise ValueError("base and treatment must have the same shape")
    if matte.shape[:2] != background.shape[:2]:
        raise ValueError("mask dimensions must match the images")
    if matte.ndim == 2:
        matte = matte[:, :, None]
    if matte.shape[2] not in {1, background.shape[2]}:
        raise ValueError("mask must have one channel or match the images")
    alpha = numpy.clip(matte.astype(numpy.float64) / (255 if numpy.issubdtype(matte.dtype, numpy.integer) else 1), 0, 1)
    result = background.astype(numpy.float64) * (1 - alpha) + foreground.astype(numpy.float64) * alpha
    return numpy.clip(numpy.rint(result), 0, 255).astype(background.dtype)
