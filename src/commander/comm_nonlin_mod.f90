module comm_nonlin_mod
  use comm_param_mod
  use comm_data_mod
  use comm_comp_mod
  use comm_chisq_mod
  use comm_gain_mod
  use comm_line_comp_mod
  use comm_diffuse_comp_mod
  implicit none

contains

!!$  subroutine sample_mono_dipole_with_mask(cpar, iter, handle)
!!$    implicit none
!!$    type(comm_params),  intent(in)    :: cpar
!!$    integer(i4b),       intent(in)    :: iter
!!$    type(planck_rng),   intent(inout) :: handle    
!!$
!!$    integer(i4b) :: i
!!$    class(comm_map),     pointer :: res
!!$    class(comm_comp),    pointer :: c
!!$    real(dp),          allocatable, dimension(:,:) :: m
!!$
!!$    ! Find monopole and dipole component
!!$    c => compList
!!$    do while (associated(c))
!!$       if (trim(c%label) /= 'md') then
!!$          c => c%next()
!!$          cycle
!!$       else
!!$          exit
!!$       end if
!!$    end do
!!$
!!$    ! Estimate monopoles and dipoles for each frequency
!!$    do i = 1, numband
!!$       ! Compute residual
!!$       res     => compute_residual(i)
!!$       m       = c%getBand(i)
!!$       res%map = res%map + m
!!$
!!$       call res%dealloc()
!!$       nullify(res)
!!$       deallocate(m)
!!$    end do
!!$    
!!$
!!$    nullify(c)
!!$
!!$
!!$    ! Sample spectral parameters for each signal component
!!$    allocate(status_fit(numband))
!!$    c => compList
!!$    do while (associated(c))
!!$       if (c%npar == 0) then
!!$          c => c%next()
!!$          cycle
!!$       end if
!!$       if (all(c%p_gauss(2,:) == 0.d0)) then
!!$          c => c%next()
!!$          cycle
!!$       end if
!!$       
!!$       do j = 1, c%npar
!!$
!!$          if (c%p_gauss(2,j) == 0.d0) cycle
!!$
!!$
!!$  end subroutine sample_mono_dipole_with_mask

  subroutine sample_nonlin_params(cpar, iter, handle)
    implicit none
    type(comm_params),  intent(in)    :: cpar
    integer(i4b),       intent(in)    :: iter
    type(planck_rng),   intent(inout) :: handle    

    integer(i4b) :: i, j, k, q, p, pl, np, nlm, out_every, num_accepted, smooth_scale, id_native, ierr, nalm_tot, ind
    integer(i4b) :: nsamp
    real(dp)     :: t1, t2, lr, ts, rg, dalm, sigma_prior
    real(dp)     :: mu, sigma, par, chisq, chisq_old, chisq_d, accept_rate, diff, chisq_prior
    integer(i4b), allocatable, dimension(:) :: status_fit   ! 0 = excluded, 1 = native, 2 = smooth
    integer(i4b)                            :: status_amp   !               1 = native, 2 = smooth
    character(len=2) :: itext, jtext
    logical :: accepted, exist
    class(comm_mapinfo), pointer :: info => null()
    class(comm_N),       pointer :: tmp  => null()
    class(comm_map),     pointer :: res  => null()
    class(comm_comp),    pointer :: c    => null()
    real(dp),          allocatable, dimension(:,:,:)   :: alm_mean_sub, alms, alm_covmat, L
    real(dp),          allocatable, dimension(:,:) :: m, mu_alm, alm_old
    real(dp),          allocatable, dimension(:) :: buffer

    integer(c_int),    allocatable, dimension(:,:) :: lm
    integer(i4b), dimension(MPI_STATUS_SIZE) :: mpistat

    call wall_time(t1)
    
    ! Initialize residual maps
    do i = 1, numband
       res             => compute_residual(i)
       data(i)%res%map =  res%map
       call res%dealloc()
       nullify(res)
    end do
    
    ! Sample spectral parameters for each signal component
    allocate(status_fit(numband))
    c => compList
    do while (associated(c))
       if (c%npar == 0) then
          c => c%next()
          cycle
       end if
       if (all(c%p_gauss(2,:) == 0.d0)) then
          c => c%next()
          cycle
       end if
       
       do j = 1, c%npar

          if (c%p_gauss(2,j) == 0.d0) cycle


          ! Add current component back into residual
!!$          call int2string(j,itext)
!!$          call data(j)%res%writeFITS('res_before'//itext//'.fits')

          if (trim(c%class) /= 'ptsrc') then
             do i = 1, numband
                allocate(m(0:data(i)%info%np-1,data(i)%info%nmaps))
                m               = c%getBand(i)
                data(i)%res%map = data(i)%res%map + m
                deallocate(m)
             end do
          end if

          ! Set up smoothed data
          select type (c)
          class is (comm_line_comp)
             if (cpar%myid_chain == 0) write(*,*) '   Sampling ', trim(c%label), ' ', trim(c%indlabel(j))
          class is (comm_diffuse_comp)
             if (cpar%myid_chain == 0) write(*,*) '   Sampling ', trim(c%label), ' ', trim(c%indlabel(j))
             call update_status(status, "nonlin start " // trim(c%label)// ' ' // trim(c%indlabel(j)))

             ! Set up type of smoothing scale
             id_native    = 0

             ! Compute smoothed residuals
             nullify(info)
             status_amp   = 0
             status_fit   = 0
             smooth_scale = c%smooth_scale(j)
             do i = 1, numband
                if (cpar%num_smooth_scales == 0) then
                   status_fit(i)   = 1    ! Native
                else
                   if (.not. associated(data(i)%N_smooth(smooth_scale)%p) .or. &
                        & data(i)%bp(0)%p%nu_c < c%nu_min_ind(j) .or. &
                        & data(i)%bp(0)%p%nu_c > c%nu_max_ind(j)) then
                      status_fit(i) = 0
                   else
                      if (.not. associated(data(i)%B_smooth(smooth_scale)%p)) then
                         status_fit(i)   = 1 ! Native
                      else
                         status_fit(i)   = 2 ! Smooth
                      end if
                   end if
                end if
                
                if (status_fit(i) == 0) then
                   ! Channel is not included in fit
                   nullify(res_smooth(i)%p)
                   nullify(rms_smooth(i)%p)
                else if (status_fit(i) == 1) then
                   ! Fit is done in native resolution
                   id_native          = i
                   info               => data(i)%res%info
                   res_smooth(i)%p    => data(i)%res
                   tmp                => data(i)%N
                   select type (tmp)
                   class is (comm_N_rms)
                      rms_smooth(i)%p    => tmp
                   end select
                else if (status_fit(i) == 2) then
                   ! Fit is done with downgraded data
                   info  => comm_mapinfo(data(i)%res%info%comm, cpar%nside_smooth(j), cpar%lmax_smooth(j), &
                        & data(i)%res%info%nmaps, data(i)%res%info%pol)
                   call smooth_map(info, .false., data(i)%B(0)%p%b_l, data(i)%res, &
                        & data(i)%B_smooth(smooth_scale)%p%b_l, res_smooth(i)%p)
                   rms_smooth(i)%p => data(i)%N_smooth(smooth_scale)%p
                end if

!!$                call int2string(i,itext)
!!$                call res_smooth(i)%p%writeFITS('res'//itext//'.fits')

             end do
             status_amp = maxval(status_fit)

             ! Compute smoothed amplitude map
             if (.not. associated(info) .or. status_amp == 0) then
                write(*,*) 'Error: No bands contribute to index fit!'
                call mpi_finalize(i)
                stop
             end if
             if (status_amp == 1) then
                ! Smooth to the beam of the last native channel
                info  => comm_mapinfo(c%x%info%comm, c%x%info%nside, c%x%info%lmax, &
                     & c%x%info%nmaps, c%x%info%pol)
                call smooth_map(info, .true., data(id_native)%B(0)%p%b_l*0.d0+1.d0, c%x, &  
                     & data(id_native)%B(0)%p%b_l, c%x_smooth)
             else if (status_amp == 2) then
                ! Smooth to the common FWHM
                info  => comm_mapinfo(c%x%info%comm, cpar%nside_smooth(j), cpar%lmax_smooth(j), &
                     & c%x%info%nmaps, c%x%info%pol)
                call smooth_map(info, .true., &
                     & data(1)%B_smooth(smooth_scale)%p%b_l*0.d0+1.d0, c%x, &  
                     & data(1)%B_smooth(smooth_scale)%p%b_l,           c%x_smooth)
             end if

             !c%x_smooth%map = c%x_smooth%map * c%F(1)%p%map

!!$             call c%x_smooth%writeFITS('x.fits')
!!$             call mpi_finalize(i)
!!$             stop
             if (c%lmax_ind > 0) then
                ! Compute smoothed spectral index maps
                allocate(c%theta_smooth(c%npar))
                do k = 1, c%npar
                   if (k == j) cycle
                   if (status_amp == 1) then ! Native resolution
                      info  => comm_mapinfo(c%x%info%comm, c%x%info%nside, &
                           & c%x%info%lmax, c%x%info%nmaps, c%x%info%pol)
                      call smooth_map(info, .false., &
                           & data(id_native)%B(0)%p%b_l*0.d0+1.d0, c%theta(k)%p, &  
                           & data(id_native)%B(0)%p%b_l,           c%theta_smooth(k)%p)
                   else if (status_amp == 2) then ! Common FWHM resolution
                      info  => comm_mapinfo(c%theta(k)%p%info%comm, cpar%nside_smooth(smooth_scale), &
                           & cpar%lmax_smooth(smooth_scale), c%theta(k)%p%info%nmaps, c%theta(k)%p%info%pol)
                      call smooth_map(info, .false., &
                           & data(1)%B_smooth(smooth_scale)%p%b_l*0.d0+1.d0, c%theta(k)%p, &  
                           & data(1)%B_smooth(smooth_scale)%p%b_l,           c%theta_smooth(k)%p)
                   end if
                end do
             end if
                
          ! Trygve spectral index sampling

          ! TODO
          ! Add prior compatibility
          ! Check cholesky values. 
          ! Read cholesky properly

          call wall_time(t1)
          if (trim(c%operation) == 'optimize') then
             ! Calls comm_diffuse_comp_mod
             call c%sampleSpecInd(handle, j)

          else if (trim(c%operation) == 'sample' .and. c%lmax_ind > 0) then
             ! Params
             nalm_tot = (c%lmax_ind+1)**2
             lr = 0.5d0 !c%p_gauss(2,j) ! Init learning rate for proposals
             out_every = 10
             nsamp = 500
             num_accepted = 0
             sigma_prior = 0.01d0

             allocate(alms(0:nsamp, 0:nalm_tot-1,info%nmaps))                         
             allocate(alm_old(0:c%theta(j)%p%info%nalm-1,info%nmaps))                         
             allocate(L(0:nalm_tot-1, 0:nalm_tot-1, c%theta(j)%p%info%nmaps)) ! Allocate cholesky matrix

             if (info%myid == 0) then
                open(69, file=trim(cpar%outdir)//'/nonlin-samples.dat', recl=10000)

                ! Read cholesky matrix. Only root needs this
                inquire(file=trim(cpar%datadir)//'/alm_cholesky.dat', exist=exist)
                if (exist) then ! If present cholesky file
                   write(*,*) "Reading cholesky matrix"
                   open(unit=11, file=trim(cpar%datadir)//'/alm_cholesky.dat')
                   read(11,*) L
                   close(11)
                else
                   write(*,*) "No cholesky matrix found"
                   L(:,:,:) = 0.d0 ! Set diagonal to 0.001
                   do p = 0, nalm_tot-1
                      do i = 1, info%nmaps
                         L(p,p,i) = 0.001 ! Set diagonal to 0.001
                      end do
                   end do
                end if
             end if

             ! Save initial alm        
             alms(:,:,:) = 0.d0
             ! Gather alms from threads to alms array with correct indices
             do pl = 1, c%theta(j)%p%info%nmaps
                call gather_alms(c%theta(j)%p%alm, alms, c%theta(j)%p%info%nalm, c%theta(j)%p%info%lm, 0, pl, pl)
                call mpi_allreduce(MPI_IN_PLACE, alms(0,:,pl), nalm_tot, MPI_DOUBLE_PRECISION, MPI_SUM, info%comm, ierr)
             end do

             call wall_time(t1)
             if (info%myid == 0) write(*,fmt='(a,i6, a, 3f7.2)') "- sample: ", 0, " - a_00: ", alms(0,0,:)/sqrt(4.d0*PI)
             do i = 1, nsamp
                chisq_prior = 0.d0
                ! Reset accepted bool
                accepted = .false.
                ! Calculate current chisq
                call compute_chisq(c%comm, chisq_fullsky=chisq_old)

                ! Sample new alms (Account for poltype)
                do pl = 1, c%theta(j)%p%info%nmaps

                   ! if sample only pol, skip T
                   if (c%poltype(j) > 1 .and. cpar%only_pol .and. pl == 1) cycle 

                   ! p already calculated if larger than poltype ( smart ;) )
                   if (pl > c%poltype(j)) cycle

                   ! Gather alms from threads to alms array with correct indices
                   call gather_alms(c%theta(j)%p%alm, alms, c%theta(j)%p%info%nalm, c%theta(j)%p%info%lm, i, pl, pl)

                   ! Send all alms to 0 (Dont allreduce because only root will do calculation)
                   call mpi_reduce(alms(i,:,pl), alms(i,:,pl), nalm_tot, MPI_DOUBLE_PRECISION, MPI_SUM, 0, info%comm, ierr)

                   ! Propose new alms
                   if (info%myid == 0) then
                      do p = 0, nalm_tot-1
                         rg = rand_gauss(handle)
                         dalm = 0.d0
                         do q = 0, nalm_tot-1
                            dalm = dalm + lr*L(p,q,pl)*rg
                         end do
                         alms(i,p,pl) = alms(i-1,p,pl) + dalm
                      end do
                   end if

                   ! Adding prior ! Is it supposed to add for all signals? Or just free ones ??? 
                   ! Currently applying same prior on all signals
                   chisq_prior = chisq_prior + ((alms(i,0,pl) - sqrt(4*PI)*c%p_gauss(1,j))/c%p_gauss(2,j))**2
                   do p = 1, nalm_tot-1
                      chisq_prior = chisq_prior + (alms(i,p,pl)/sigma_prior)**2
                   end do
                   
                   ! Broadcast proposed alms from root
                   call mpi_bcast(alms(i,:,pl), nalm_tot, MPI_DOUBLE_PRECISION, 0, c%comm, ierr)                   
                   
                   ! Save to correct poltypes
                   if (c%poltype(j) == 1) then      ! {T+E+B}
                      do q = 1, c%theta(j)%p%info%nmaps
                         alms(i,:,q) = alms(i,:,pl) ! Save to all maps
                         call distribute_alms(c%theta(j)%p%alm, alms, c%theta(j)%p%info%nalm, c%theta(j)%p%info%lm, i, q, q)
                      end do
                   else if (c%poltype(j) == 2) then ! {T,E+B}
                      if (pl == 1) then
                         call distribute_alms(c%theta(j)%p%alm, alms, c%theta(j)%p%info%nalm, c%theta(j)%p%info%lm, i, pl, 1)
                      else
                         do q = 2, c%theta(j)%p%info%nmaps
                            alms(i,:,q) = alms(i,:,pl)
                            call distribute_alms(c%theta(j)%p%alm, alms, c%theta(j)%p%info%nalm, c%theta(j)%p%info%lm, i, q, q)                            
                         end do 
                      end if                    
                   else if (c%poltype(j) == 3) then ! {T,E,B}
                      call distribute_alms(c%theta(j)%p%alm, alms, c%theta(j)%p%info%nalm, c%theta(j)%p%info%lm, i, pl, pl)
                   end if
                end do
 
                ! Update mixing matrix with new alms
                call c%updateMixmat

                ! Calculate proposed chisq
                call compute_chisq(c%comm, chisq_fullsky=chisq)

                ! Accept/reject test
                if (info%myid == 0) then
                   chisq = chisq + chisq_prior
                   diff = chisq_old-chisq
                   if ( chisq > chisq_old ) then                 
                      ! Small chance of accepting this too
                      ! Avoid getting stuck in local mminimum
                      accepted = (rand_uni(handle) < exp(0.5d0*diff))
                   else
                      accepted = .true.
                   end if
                end if

                ! Broadcast result of accept/reject test
                call mpi_bcast(accepted, 1, MPI_LOGICAL, 0, c%comm, ierr)
                ! Briadcast chisq adjusted with prior
                call mpi_bcast(chisq, 1,  MPI_DOUBLE_PRECISION, 0, c%comm, ierr)
                
                ! Count accepted, if rejected revert changes.
                if (accepted) then
                   num_accepted = num_accepted + 1
                else
                   ! If rejected, restore old values
                   do pl = 1, c%theta(j)%p%info%nmaps
                      call distribute_alms(c%theta(j)%p%alm, alms, c%theta(j)%p%info%nalm, info%lm, i-1, pl, pl)
                   end do
                   alms(i,:,:) = alms(i-1,:,:)
                   call c%updateMixmat                
                   chisq = chisq_old
               end if

                ! Write to screen first iter
                if (i == 1) then
                   if (info%myid == 0) write(*,fmt='(a,i6, a, f16.2, a, 3f7.2)') "- sample: ", i, " - chisq: " , chisq, " - a_00: ", alms(i,0,:)/sqrt(4.d0*PI)
                   chisq_d = chisq
                end if

                ! Write to screen
                if (mod(i,out_every) == 0) then
                   diff = chisq_d - chisq ! Output diff
                   call wall_time(t2)
                   ts = (t2-t1)/DFLOAT(out_every) ! Average time per sample
                   if (info%myid == 0) write(*,fmt='(a,i6, a, f16.2, a, f10.2, a, f7.2, a, 3f7.2)') "- sample: ", i, " - chisq: " , chisq, " - diff: ", diff, " - time/sample: ", ts, " - a_00: ", alms(i,0,:)/sqrt(4.d0*PI)
                   call wall_time(t1)
                   chisq_d = chisq
                end if

                ! Adjust learning rate every 100th
                if (mod(i, 100) == 0) then 
                   ! Accept rate
                   accept_rate = num_accepted/100.d0
                   num_accepted = 0

                   ! Write to screen
                   if (info%myid == 0) write(*, fmt='(a, f5.3)') "- accept rate ", accept_rate
                   
                   ! Adjusrt lr
                   if (accept_rate < 0.2) then                 
                      lr = lr*0.5d0
                      if (info%myid == 0) write(*,fmt='(a,f10.5)') "Reducing lr -> ", lr
                   else if (accept_rate > 0.8) then
                      lr = lr*2.0d0
                      if (info%myid == 0) write(*,fmt='(a,f10.5)') "Increasing lr -> ", lr
                   end if
                end if

                ! Output samples, chisq, alms to file
                if (info%myid == 0) write(69, *) i, chisq, alms(i,:,:)
             end do
             !deallocate(sigma_prior)

             ! Calculate cholesky
             ! Output like nprocs*nalm:+k, Does not work. Need to be saved in order to be distributed correctly
             if (info%myid == 0) then! At this point, id=0 should have all values
                allocate(alm_covmat(0:nalm_tot-1, 0:nalm_tot-1, c%theta(j)%p%info%nmaps))
                allocate(alm_mean_sub(nsamp, 0:nalm_tot-1,  c%theta(j)%p%info%nmaps))
                allocate(mu_alm(0:nalm_tot-1, c%theta(j)%p%info%nmaps))
                
                ! Calculate covariance matrix
                do q = 0, nalm_tot-1 ! Calculate means
                   mu_alm(q,:) = 0.d0
                   do p = 1, nsamp
                      mu_alm(q,:) = mu_alm(q,:) + alms(p, q, :)/DFLOAT(nsamp)
                   end do
                end do

                do p = 1, nsamp ! Subtract means
                   alm_mean_sub(p,:,:) = alms(p,:,:) - mu_alm
                end do
                
                do p = 1, c%theta(j)%p%info%nmaps
                   alm_covmat(:,:,p) = matmul(alm_mean_sub(:,:,p), transpose(alm_mean_sub(:,:,p))) / (nsamp-1)
                end do

                deallocate(mu_alm, alm_mean_sub)
                
                L(:,:,:) = 0.d0
                do p = 1, c%theta(j)%p%info%nmaps
                   call cholesky_decompose(alm_covmat(:,:,p), L(:,:,p), ierr)
                end do

                open(5, file=trim(cpar%outdir)//'/alm_cholesky.dat', recl=10000)
                open(6, file=trim(cpar%outdir)//'/alm_covmat.dat', recl=10000)
                write(5, *) L
                write(6, *) alm_covmat
                close(5)
                close(6)
                close(69)
                
             end if

             deallocate(alms)
          end if
          end select

          ! Clean up temporary data structures
          select type (c)
          class is (comm_line_comp)
          class is (comm_diffuse_comp)
             
             if (associated(c%x_smooth)) then
                call c%x_smooth%dealloc()
                nullify(c%x_smooth)
             end if
             do k = 1, c%npar
                if (k == j) cycle
                if (allocated(c%theta_smooth)) then
                   if (associated(c%theta_smooth(k)%p)) then
                      call c%theta_smooth(k)%p%dealloc()
                   end if
                end if
             end do
             if (allocated(c%theta_smooth)) deallocate(c%theta_smooth)
             do i = 1, numband
                if (.not. associated(rms_smooth(i)%p)) cycle
                if (status_fit(i) == 2) then
                   call res_smooth(i)%p%dealloc()
                end if
                nullify(res_smooth(i)%p)
             end do

             smooth_scale = c%smooth_scale(j)
             if (cpar%num_smooth_scales > 0) then
                if (cpar%fwhm_postproc_smooth(smooth_scale) > 0.d0) then
                   ! Smooth index map with a postprocessing beam
                   !deallocate(c%theta_smooth)
                   allocate(c%theta_smooth(c%npar))
                   info  => comm_mapinfo(c%theta(j)%p%info%comm, cpar%nside_smooth(smooth_scale), &
                        & cpar%lmax_smooth(smooth_scale), c%theta(j)%p%info%nmaps, c%theta(j)%p%info%pol)
                   call smooth_map(info, .false., &
                        & data(1)%B_postproc(smooth_scale)%p%b_l*0.d0+1.d0, c%theta(j)%p, &  
                        & data(1)%B_postproc(smooth_scale)%p%b_l,           c%theta_smooth(j)%p)
                   c%theta(j)%p%map = c%theta_smooth(j)%p%map
                   call c%theta_smooth(j)%p%dealloc()
                   deallocate(c%theta_smooth)
                end if
             end if

             call update_status(status, "nonlin stop " // trim(c%label)// ' ' // trim(c%indlabel(j)))

          end select

          ! Subtract updated component from residual
          if (trim(c%class) /= 'ptsrc') then
             do i = 1, numband
                allocate(m(0:data(i)%info%np-1,data(i)%info%nmaps))
                m               = c%getBand(i)
                data(i)%res%map = data(i)%res%map - m
                deallocate(m)
             end do
          end if

!!$          call int2string(j,itext)
!!$          call data(j)%res%writeFITS('res_after'//itext//'.fits')


       end do

       ! Loop to next component
       c => c%next()
    end do
    deallocate(status_fit)

!!$    call mpi_finalize(i)
!!$    stop

    ! Sample calibration factors
    do i = 1, numband
       if (.not. data(i)%sample_gain) cycle
       call sample_gain(cpar%operation, i, cpar%outdir, cpar%mychain, iter, handle)
    end do


    ! Update mixing matrices
    if (any(data%sample_gain)) then
       c => compList
       do while (associated(c))
          call c%updateMixmat
          c => c%next()
       end do
    end if

    call wall_time(t2)
    if (cpar%myid_chain == 0) write(*,*) 'CPU time specind = ', real(t2-t1,sp)
    
  end subroutine sample_nonlin_params


  subroutine gather_alms(alm, alms, nalm, lm, i, pl, pl_tar)
    implicit none

    real(dp), dimension(0:,1:),    intent(in)    :: alm
    integer(c_int), dimension(1:,0:), intent(in) :: lm
    real(dp), dimension(0:,0:,1:), intent(inout) :: alms
    integer(i4b),                intent(in)    :: nalm, i, pl, pl_tar
    integer(i4b) :: k, l, m, ind

    do k = 0, nalm-1
       ! Gather all alms
       l = lm(1,k)
       m = lm(2,k)
       ind = l**2 + l + m
       alms(i,ind,pl_tar) = alm(k,pl)
    end do

  end subroutine gather_alms

  subroutine distribute_alms(alm, alms, nalm, lm, i, pl, pl_tar)
    implicit none

    real(dp), dimension(0:,1:),    intent(inout)    :: alm
    integer(c_int), dimension(1:,0:), intent(in)   :: lm
    real(dp), dimension(0:,0:,1:),  intent(in)       :: alms
    integer(i4b),                intent(in)       :: nalm, i, pl, pl_tar
    integer(i4b) :: k, l, m, ind
    
    do k = 0, nalm-1
       ! Distribute alms
       l = lm(1,k)
       m = lm(2,k)
       ind = l**2 + l + m
       alm(k,pl_tar) = alms(i,ind,pl)
    end do

  end subroutine distribute_alms



end module comm_nonlin_mod
