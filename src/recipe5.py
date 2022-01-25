try:
    from typing import Callable  # to please lint...
except ImportError:
    ...
from recipe import Recipe, Stage


def get_recipe(callback: Callable[..., None]) -> Recipe:
    return Recipe('Brönald #5 - Abraham',
                  # stage name, duration [s], target temperature [°C], (manual action to perform at end of stage)
                  [Stage('Preheat', 0, 65, 'Add malt and cooked oats'),
                   Stage('Maichen phase1', 30 * 60, 63),
                   Stage('Maichen phase2', 15 * 60, 67),
                   Stage('Maichen phase3', 30 * 60, 72),
                   Stage('Maichen phase4', 5 * 60, 77, 'Filter/remove grains'),
                   Stage('Boil phase1', 30 * 60, 100, 'Add first hops'),
                   Stage('Boil phase2', 50 * 60, 100, 'Add rest of hops and sugar'),
                   Stage('Boil phase3', 10 * 60, 100, 'Whirlpool and start cooling'),
                   Stage('Cooling', 0, 20, 'Transfer wort to fermentation vessel and add yeast', False)],
                  callback)
