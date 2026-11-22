# Tracker MACD capability reconciliation — Release 745

The actions listed here are implemented existing workflows (741 and earlier)
except Water correction, introduced in 745. Move is contextual, not mandatory
for each record. Irreversible operations remain guarded.

| Record | Move / Reassign | Add | Edit / Change | Delete / Stop | Historical boundary |
| --- | --- | --- | --- | --- | --- |
| Medication/supplement | Schedule/meal association | Item | Item and catalog facts | Archive / confirmed delete | Dependent records checked |
| Regimen schedule | Shift day, timing | Schedule | Edit schedule | Stop, guarded empty-schedule delete | Actual intake retained |
| Regimen intake | Correct timestamp | Log intake | Edit intake | Delete with private audit | Does not rewrite prescription |
| Food logged entry | Move date/meal | Log food | Edit serving/meal/details | Delete | Saved product unaffected |
| Food saved product | Repeat by date | Save | Edit | Delete | Logged history independent |
| Meal template | Log on selected day | Save | Rename | Delete | Historic food entries remain |
| Water entry | **Move to correct date** | Log water | **Correct ounces** | Confirmed remove | Record ID/day-scoped UPDATE; other records intact |
| Workout session | Correct backdated date | Start/log past | Edit completed session | Delete | Related sets handled |
| Workout routine | Reorder/substitute | Create/duplicate | Rename/edit exercises | Delete only when unused | Session links protected |
| Workout equipment | Contextual replace | Create | Edit settings | Delete only when unreferenced | Set history protected |
| Workout set | Reorder by routine | Log | Correct set | Remove set | Corrections scoped |
| Supplies/categories | Reassign compatible unused stock | Add | Edit label/unit | Guarded delete | Ledger and built-in categories protected |
| Vials | Lifecycle/reassign | Create/bulk | Edit details | Guarded delete | Doses, preparations and COAs checked |
| Prepared blends | Sources and draws | Create | Correct withdrawal | No unsafe whole-blend Delete | Custody/source transfer immutable |
| COAs | Assign/reassign to vial | Create/import | Edit metadata/docs/types | Guarded delete | Shared provenance kept |
| Labs | Correct report date | Create/import | Edit report/analytes | Guarded delete | Document integrity kept |
| Protocol/calendar | Schedule/reorder/duplicate | Add | Edit plan | Stop/delete; hide projections | Actual dose logs independent |
| Notes | Navigation/source association | Add | Edit content/history | Confirmed delete | Private metadata-only deletion audit |

Visible native actions are preferred. Disabled/unsafe operations are not
replaced with fake buttons. Long-term owner-scoping and end-to-end user
testing remain ongoing, separate from this capability inventory.
