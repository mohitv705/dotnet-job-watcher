from providers import ashby, generic, greenhouse, icims, lever, smartrecruiters, successfactors, workday

PROVIDERS = {
    "ashby": ashby.fetch,
    "generic": generic.fetch,
    "greenhouse": greenhouse.fetch,
    "icims": icims.fetch,
    "lever": lever.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "successfactors": successfactors.fetch,
    "workday": workday.fetch,
}
