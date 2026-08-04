from providers import (
    accenture,
    ashby,
    generic,
    greenhouse,
    icims,
    lever,
    smartrecruiters,
    successfactors,
    workday,
)

PROVIDERS = {
    "accenture": accenture.fetch,
    "ashby": ashby.fetch,
    "generic": generic.fetch,
    "greenhouse": greenhouse.fetch,
    "icims": icims.fetch,
    "lever": lever.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "successfactors": successfactors.fetch,
    "workday": workday.fetch,
}