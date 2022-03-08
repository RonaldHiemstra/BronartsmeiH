try:
    from typing import Callable  # to please lint...
except ImportError:
    ...
from recipe import Recipe, Stage


def get_recipe(callback: Callable[..., None]) -> Recipe:
    return Recipe('Brönald #5 - Abraham',
                  # stage name, duration [s], target temperature [°C], (manual action to perform at end of stage)
                  [Stage('Preheat', 0, 65, 'Add malt and cooked oats'),
                   Stage('Maichen phase1', 30 * 60, 63),  # TODO: start unconditionally
                   Stage('Maichen phase2', 15 * 60, 67),  # TODO: start unconditionally
                   Stage('Maichen phase3', 30 * 60, 72),  # TODO: start unconditionally
                   Stage('Maichen phase4', 5 * 60, 77, 'Filter/remove grains'),  # TODO: start unconditionally
                   Stage('Boil phase1', 30 * 60, 100, 'Add first hops'),
                   Stage('Boil phase2', 50 * 60, 100, 'Add rest of hops and sugar'),  # TODO: start unconditionally
                   Stage('Boil phase3', 10 * 60, 100, 'Whirlpool and start cooling'),  # TODO: start unconditionally
                   Stage('Cooling', 0, 19, 'Transfer wort to fermentation vessel and add yeast', False)],
                  callback)
