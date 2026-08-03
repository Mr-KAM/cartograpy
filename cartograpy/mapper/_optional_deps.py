try:
    import contextily as ctx
    HAS_CONTEXTILY = True
except ImportError:
    HAS_CONTEXTILY = False
try:
    from matplotlib_scalebar.scalebar import ScaleBar as MplScaleBar
    HAS_MPL_SCALEBAR = True
except ImportError:
    HAS_MPL_SCALEBAR = False
try:
    from matplotlib_map_utils.core.north_arrow import (
        NorthArrow as MmuNorthArrow,
        north_arrow as mmu_north_arrow,
    )
    from matplotlib_map_utils.core.scale_bar import (
        ScaleBar as MmuScaleBar,
        scale_bar as mmu_scale_bar,
    )
    from matplotlib_map_utils.core.inset_map import (
        InsetMap as MmuInsetMap,
        ExtentIndicator as MmuExtentIndicator,
        DetailIndicator as MmuDetailIndicator,
        inset_map as mmu_inset_map,
        indicate_extent as mmu_indicate_extent,
        indicate_detail as mmu_indicate_detail,
    )
    from matplotlib_map_utils import set_size as mmu_set_size
    HAS_MAP_UTILS = True
    # Patch: matplotlib-map-utils uses type()==match instead of isinstance()
    # which rejects cartopy GeoAxes (a subclass of matplotlib Axes).
    try:
        from matplotlib_map_utils.validation.inset_map import _VALIDATE_EXTENT
        _orig_validate_type = _VALIDATE_EXTENT["pax"]["func"]
        def _isinstance_validate_type(prop, val, match, none_ok=False):
            if not none_ok and val is None:
                raise ValueError(f"None is not a valid value for {prop}")
            if none_ok and val is None:
                return val
            if not isinstance(val, match):
                raise ValueError(
                    f"'{val}' is not a valid value for {prop}, "
                    f"please provide an object of type {match}"
                )
            return val
        _VALIDATE_EXTENT["pax"]["func"] = _isinstance_validate_type
        _VALIDATE_EXTENT["bax"]["func"] = _isinstance_validate_type
    except Exception:
        pass
except ImportError:
    HAS_MAP_UTILS = False
