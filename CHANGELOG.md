# Changelog

## 0.1.0 (2026-02-23)


### Features

* add endpoint to bulk insert specimens, update sample table to only require bpa_sample_id for derived samples ([248de31](https://github.com/AustralianBioCommons/atol-canopy/commit/248de31a587b8142512fe21a8d43a47968833c52))
* add endpoint to look up specimen by specimen_id + tax_id ([96910e8](https://github.com/AustralianBioCommons/atol-canopy/commit/96910e87daf446538264022fdd417852047fcb98))
* add function to determine data_type for an assembly, and a matching endpoint ([c1f54a8](https://github.com/AustralianBioCommons/atol-canopy/commit/c1f54a852ff16c55bd9ed6cbb19df6f97fa40d82))
* add new organism fields ([6bbef3a](https://github.com/AustralianBioCommons/atol-canopy/commit/6bbef3ae92a96128c975926b9a58252343affc13))
* add new organism fields and improve broker endpoints ([cc804f5](https://github.com/AustralianBioCommons/atol-canopy/commit/cc804f5dfc7a3e94629618c7195c64b85a0599d3))
* add POST /claim endpoint to lease individual sample/experiments/reads objs (no organism_key required) ([da14705](https://github.com/AustralianBioCommons/atol-canopy/commit/da147059ae6c5200b35d04f9e332f8764b89ed14))
* add specimen-level samples ([0d61033](https://github.com/AustralianBioCommons/atol-canopy/commit/0d61033a0887b2bd1bf075884e360d3501fa56af))
* add specimen/derived samples to the db schema, models, endpoints ([bf2840c](https://github.com/AustralianBioCommons/atol-canopy/commit/bf2840cd4bac8aa78dcecf461059bebc80419fa2))
* add uniqueness constraint on tax_id + specimen_id for specimen samples ([2dcbf1a](https://github.com/AustralianBioCommons/atol-canopy/commit/2dcbf1af19b62c7f01451fe5cd79c472824035b8))
* add version endpoint ([a45650f](https://github.com/AustralianBioCommons/atol-canopy/commit/a45650f58bbb3b36cb122b8b6fde9e5d62b4c45a))
* generate assembly manifest (for pacbio and hi-C reads) ([665a633](https://github.com/AustralianBioCommons/atol-canopy/commit/665a63351b739a6533b44dffdecc2bceee09fbeb))
* implement genome notes with versioning ([b865bac](https://github.com/AustralianBioCommons/atol-canopy/commit/b865bac9cedc8f910d9d895e0acced0a1c002ec6))
* improve error messaging for bulk-insert endpoints ([c5aca3e](https://github.com/AustralianBioCommons/atol-canopy/commit/c5aca3e7ebbddbb65303d3d30858b88a5fe74853))
* redesign genome notes and assemblies ([dd7115e](https://github.com/AustralianBioCommons/atol-canopy/commit/dd7115eb6aaf183739f942b9b6df7e32e1e6ce59))
* update assembly models to meet new requirements ([ee75d58](https://github.com/AustralianBioCommons/atol-canopy/commit/ee75d58835cc9fe84e841662e59d650f5b617b9d))
* update assembly models to meet new(est) requirements ([f936379](https://github.com/AustralianBioCommons/atol-canopy/commit/f9363790b6a83e10f38686b5e79a302ea434bb04))
* uplift error handling, tests, auth policy ([9120188](https://github.com/AustralianBioCommons/atol-canopy/commit/912018880affcc57dd6f20604ea9f0f32121becd))


### Bug Fixes

* address codepilot review ([9f8253b](https://github.com/AustralianBioCommons/atol-canopy/commit/9f8253b14f45b92be297bf59db787dcbd2324018))
* consolidate auth policy, add centralised error handling module and pagination ([9df3b9f](https://github.com/AustralianBioCommons/atol-canopy/commit/9df3b9f020a25136841a907071ba56a71cdf3b8d))
* consolidate auth policy, add centralised error handling module and pagination ([1db5e59](https://github.com/AustralianBioCommons/atol-canopy/commit/1db5e5938632f31769b868ccc0c9d09548e7fa74))
* Dockerfile ([01f1be5](https://github.com/AustralianBioCommons/atol-canopy/commit/01f1be5d597e4655cdf4bd52a82030a0638f011b))
* enforce 72-byte limit at user create/update ([44b9bbb](https://github.com/AustralianBioCommons/atol-canopy/commit/44b9bbbb44db3f6e771bb2afb3b575f8048e4109))
* enforce expiry of leased items on before new lease request ([91dbbbc](https://github.com/AustralianBioCommons/atol-canopy/commit/91dbbbc48c24394e9216c7ce680b9aeed517099e))
* fix db readiness probe ([175f9d2](https://github.com/AustralianBioCommons/atol-canopy/commit/175f9d2bae5075688a005521e360c3f3b885e170))
* import if an experiment already exists in the db, still add any valid related runs to the db ([b053cee](https://github.com/AustralianBioCommons/atol-canopy/commit/b053ceeeaea245d537fec4b151f5be0660d7acbb))
* improve errors returned from ingestion endpoints ([32161f4](https://github.com/AustralianBioCommons/atol-canopy/commit/32161f4b62ab8ff8da7b013fb2b1f35b26522eee))
* improve test for the 72 byte password limitation in bcrypt ([974b29d](https://github.com/AustralianBioCommons/atol-canopy/commit/974b29d96d56b68fd8d12901915e6e6b4435510b))
* rename testing files ([30bb35d](https://github.com/AustralianBioCommons/atol-canopy/commit/30bb35d8b1349abb0427e8723a05d9e1db096d21))
* resolve passlib + bcrypt incompatibility ([6ad8cd0](https://github.com/AustralianBioCommons/atol-canopy/commit/6ad8cd045da81f6171649973cf16d7c2d9c7fe7e))
* update references to organism key, and resolve conflicting status field ([6b3bdc4](https://github.com/AustralianBioCommons/atol-canopy/commit/6b3bdc48a0ca8badf34ff0ed951b86a93143dbbd))
* update tests ([f85fe77](https://github.com/AustralianBioCommons/atol-canopy/commit/f85fe77033b43288a03e42b6dc7dc0a22c09a3cf))


### Documentation

* add PR template for repo ([7a4d695](https://github.com/AustralianBioCommons/atol-canopy/commit/7a4d69595cc622fa860086d630d8e7f0776352db))
