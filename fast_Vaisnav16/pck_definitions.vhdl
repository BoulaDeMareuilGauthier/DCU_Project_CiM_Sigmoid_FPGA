library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package pck_definitions is
  constant num_bits : integer := 16;
  constant num_bits_int_part : integer := 4;
  constant num_bits_frac_part : integer := num_bits - num_bits_int_part;
  constant zero : signed ( ( num_bits - 1 ) downto 0 ) := to_signed( 0, num_bits );
  constant one : signed ( ( num_bits - 1 ) downto 0 ) := to_signed( 4096, num_bits );
  constant limit_5120 : signed ( ( num_bits - 1 ) downto 0 ) := to_signed( 20480, num_bits );
  constant limit_2432 : signed ( ( num_bits - 1 ) downto 0 ) := to_signed( 9728, num_bits );
  constant limit_1024 : signed ( ( num_bits - 1 ) downto 0 ) := to_signed( 4096, num_bits );
  constant indep_864 : signed ( ( num_bits - 1 ) downto 0 ) := to_signed( 3456, num_bits );
  constant indep_640 : signed ( ( num_bits - 1 ) downto 0 ) := to_signed( 2560, num_bits );
  constant indep_512 : signed ( ( num_bits - 1 ) downto 0 ) := to_signed( 2048, num_bits );
end package pck_definitions;
