library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.pck_definitions.all;

entity sigmoide is
  port (
    ck : in bit;
    x : in  signed ( ( num_bits - 1 ) downto 0 );
    y : out signed ( ( num_bits - 1 ) downto 0 ));
end sigmoide;

architecture calcula of sigmoide is
begin  -- calcula
  calcula_saida: process( ck )
    variable abs_x, y_tmp, tmp_small : signed ( ( num_bits - 1 ) downto 0 );
    variable tmp_large : signed( 2 * num_bits - 1 downto 0 );
  begin  -- process calcula_saida
    if ck = '1' then
      abs_x := abs( x );
      if abs_x >= limit_5120 then
        y_tmp := one;
      elsif abs_x >= limit_2432 then
        y_tmp := shift_right( abs_x, 5 ) + indep_864;
      elsif abs_x >= limit_1024 then
        y_tmp := shift_right( abs_x, 3 ) + indep_640;
      else
        y_tmp := shift_right( abs_x, 2 ) + indep_512;
      end if;
      if x( num_bits - 1 ) = '0' then
        y <= y_tmp;
      else
        y <= one - y_tmp;
      end if;
    end if;
  end process calcula_saida;
end calcula;
