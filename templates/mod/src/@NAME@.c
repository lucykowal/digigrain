/* @NAME@: starting point. Prefix every global with @CNAME@_ (symbols are shared across all loaded mods).
 * Shared code lives in common/ (#include "common/include/x.h"); never include another mod. */

void @CNAME@_tick(void *ctrl)
{
	(void)ctrl;
}
