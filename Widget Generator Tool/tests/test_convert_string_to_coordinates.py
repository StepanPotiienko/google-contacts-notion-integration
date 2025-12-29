import unittest

import convert_string_to_coordinates

class TestAddressConvertingMethods(unittest.TestCase):

    def test_split_string(self):
      self.assertEqual(convert_string_to_coordinates.split_address("вул. Хрещатик, 22, Київ"), ["вул. Хрещатик", "22", "Київ"])

if __name__ == '__main__':
    unittest.main(verbosity=2)