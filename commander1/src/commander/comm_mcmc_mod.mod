  �$  ^   k820309    l          18.0        �J�\                                                                                                          
       comm_mcmc_mod.f90 COMM_MCMC_MOD              JOINT_THRESHOLD COMM_MASTER MYID_MASTER ROOT NUMPROCS NSTEP VERBOSITY LMIN_BIN LMAX_BIN SPEC_BIN OPERATION CDIR CLS_PROP S_PROP                      @                              
                        �   @                              
                            @                              
                         @               @                '8                   #CMB_AMP    #FG_AMP    #TEMP_AMP              �                                                            
            &                   &                                                     �                                          `                 
            &                   &                   &                                                     �                                          �                 
            &                   &                                                             @                                '                     #X 	   #Y 
   #Z    #W    #GSET    #EMPTY                 � $                             	                                � $                             
                               � $                                                            � $                                                            � $                                            
                � $                                                                 @                               '                                                                                                                                                                                                                                                                                     
                 
                    JxޱA        2.99792458D8                                                                                                                                                                                   
          D            1140850688#         @                                                   
   #PARFILE    #PARNAME    #PAR_INT    #PAR_CHAR    #PAR_STRING    #PAR_SP    #PAR_DP    #PAR_LGT    #PAR_PRESENT    #DESC                                                                  1                                                               1                                                                                                                     1                                                               1                                                	                                                      
                                                                                                                                                                                 1                                                                                                     !            +                                          "                                   &                   &                                                   #         @                                  #                    #VECTOR $             
                                 $     8              #GENVEC                                              %                                   &                   &                                           %         @                               &                 	   
       #HANDLE '   #LNL (   #X_INIT *   #PRIOR +   #STATUS ,   #NEVAL -   #X_N_OUT .   #S_N_OUT /   #BOUNDS_OK 0                                              '                     #PLANCK_RNG    %         @                                (                    
       #X )             
                                )     
                
                                *                   
              &                                                                                     +                   
     p          p            p                                                                    ,                                                      -                                                    .                   
               &                                                                                   /                   
               &                                                     
                                0           #         @                                  1                    #MAP_ID 2   #COEFF 3   #OUTPUT_STATS 4   #CHISQ_FULLSKY 5   #CHISQ_HIGHLAT 6   #CHISQ_MAP 7   #CHISQ_RMS 8   #CHISQ_BAND 9   #NU_BAND :   #CHAIN ;   #ITER <             
                                 2                     
                                  3     8             #GENVEC              
                                4                                                     5     
                                                 6     
                      �                           7                   
               & p                   & p                                                                                    8     
                      �                           9                   
               & p                                                         �                           :                   
               & p                                                    
                                ;                     
                                <           %         @                               =                            #         @                                  >                    #V1 ?   #V2 @             
                                  ?     8             #GENVEC              
                                 @     8              #GENVEC    #         @                                  A                    #VECTOR B             
                                 B     8              #GENVEC                                               C            #         @                                  D                    #CL E   #S F             
      �                           E                   
 K             & p                                                        �                           F                   
 L              & p                  & p                                          #         @                                  G                    #A H   #POW I             
    �                           H                   
 (              & p                  & p                                                    
                                 I     
      %         @                               J                           #L K   #M L             
                                 K                     
                                 L           #         @                                   M                    #PARAMFILE N   #COMM_MASTER_IN O             
@ @                              N     �                                
                                 O           #         @                                   P                     #         @                                   Q                    #RNG_HANDLE R   #CL S   #S T             
D @                               R                     #PLANCK_RNG              
D@   �                           S                   
               & p                   & p                                                    
D @                               T     8              #GENVEC    %         @  @                            U                    
       #CL V                                                                                             
  @                              V     
      #         @                                  W                    #LMIN X   #LMAX Y   #SPEC Z   #CL [   #ALMS \             
                                 X                     
                                 Y                     
                                 Z                     
                                 [     
                
D     �                           \                   
 	              & p                  & p                                             �   (      fn#fn #   �   �   b   uapp(COMM_MCMC_MOD    X  @   J   COMM_MP_MOD    �  @   J   ARS_MOD !   �  @   J   COMM_CL_UTIL_MOD '     w       GENVEC+COMM_GENVEC_MOD /   �  �   a   GENVEC%CMB_AMP+COMM_GENVEC_MOD .   ;  �   a   GENVEC%FG_AMP+COMM_GENVEC_MOD 0   �  �   a   GENVEC%TEMP_AMP+COMM_GENVEC_MOD "   �  �       PLANCK_RNG+RNGMOD $   ,  H   a   PLANCK_RNG%X+RNGMOD $   t  H   a   PLANCK_RNG%Y+RNGMOD $   �  H   a   PLANCK_RNG%Z+RNGMOD $     H   a   PLANCK_RNG%W+RNGMOD '   L  H   a   PLANCK_RNG%GSET+RNGMOD (   �  H   a   PLANCK_RNG%EMPTY+RNGMOD '   �  P       #UNLPOLY+ISO_C_BINDING !   ,  p       DP+HEALPIX_TYPES "   �  p       I4B+HEALPIX_TYPES      |       C+COMM_BP_MOD "   �  p       LGT+HEALPIX_TYPES -   �  z       MPI_COMM_WORLD+MPI_ALM_TOOLS )   r	  �       GET_PARAMETER+COMM_UTILS 1   ?
  L   a   GET_PARAMETER%PARFILE+COMM_UTILS 1   �
  L   a   GET_PARAMETER%PARNAME+COMM_UTILS 1   �
  @   a   GET_PARAMETER%PAR_INT+COMM_UTILS 2     L   a   GET_PARAMETER%PAR_CHAR+COMM_UTILS 4   c  L   a   GET_PARAMETER%PAR_STRING+COMM_UTILS 0   �  @   a   GET_PARAMETER%PAR_SP+COMM_UTILS 0   �  @   a   GET_PARAMETER%PAR_DP+COMM_UTILS 1   /  @   a   GET_PARAMETER%PAR_LGT+COMM_UTILS 5   o  @   a   GET_PARAMETER%PAR_PRESENT+COMM_UTILS .   �  L   a   GET_PARAMETER%DESC+COMM_UTILS ,   �  @       NUM_CL_BIN+COMM_CL_UTIL_MOD $   ;  @       NSPEC+COMM_DATA_MOD -   {  �       CL_BIN_STAT+COMM_CL_UTIL_MOD 0   '  T       ALLOCATE_GENVEC+COMM_GENVEC_MOD 7   {  T   a   ALLOCATE_GENVEC%VECTOR+COMM_GENVEC_MOD )   �  �       CL_BINS+COMM_CL_UTIL_MOD #   s  �       SAMPLE_ARS+ARS_MOD *   /  X   a   SAMPLE_ARS%HANDLE+ARS_MOD '   �  W      SAMPLE_ARS%LNL+ARS_MOD )   �  @   a   SAMPLE_ARS%LNL%X+ARS_MOD *     �   a   SAMPLE_ARS%X_INIT+ARS_MOD )   �  �   a   SAMPLE_ARS%PRIOR+ARS_MOD *   >  @   a   SAMPLE_ARS%STATUS+ARS_MOD )   ~  @   a   SAMPLE_ARS%NEVAL+ARS_MOD +   �  �   a   SAMPLE_ARS%X_N_OUT+ARS_MOD +   J  �   a   SAMPLE_ARS%S_N_OUT+ARS_MOD -   �  @   a   SAMPLE_ARS%BOUNDS_OK+ARS_MOD *     �       COMPUTE_CHISQ+COMM_MP_MOD 1   �  @   a   COMPUTE_CHISQ%MAP_ID+COMM_MP_MOD 0   =  T   a   COMPUTE_CHISQ%COEFF+COMM_MP_MOD 7   �  @   a   COMPUTE_CHISQ%OUTPUT_STATS+COMM_MP_MOD 8   �  @   a   COMPUTE_CHISQ%CHISQ_FULLSKY+COMM_MP_MOD 8     @   a   COMPUTE_CHISQ%CHISQ_HIGHLAT+COMM_MP_MOD 4   Q  �   a   COMPUTE_CHISQ%CHISQ_MAP+COMM_MP_MOD 4   �  @   a   COMPUTE_CHISQ%CHISQ_RMS+COMM_MP_MOD 5   =  �   a   COMPUTE_CHISQ%CHISQ_BAND+COMM_MP_MOD 2   �  �   a   COMPUTE_CHISQ%NU_BAND+COMM_MP_MOD 0   ]  @   a   COMPUTE_CHISQ%CHAIN+COMM_MP_MOD /   �  @   a   COMPUTE_CHISQ%ITER+COMM_MP_MOD "   �  P       GETLUN+COMM_UTILS 1   -  X       GENVEC_SET_EQUAL+COMM_GENVEC_MOD 4   �  T   a   GENVEC_SET_EQUAL%V1+COMM_GENVEC_MOD 4   �  T   a   GENVEC_SET_EQUAL%V2+COMM_GENVEC_MOD 2   -  T       DEALLOCATE_GENVEC+COMM_GENVEC_MOD 9   �  T   a   DEALLOCATE_GENVEC%VECTOR+COMM_GENVEC_MOD $   �  @       NMAPS+COMM_DATA_MOD       W       CL2S+COMM_UTILS #   l  �   a   CL2S%CL+COMM_UTILS "   �  �   a   CL2S%S+COMM_UTILS 2   �  X       COMPUTE_HERMITIAN_ROOT+MATH_TOOLS 4      �   a   COMPUTE_HERMITIAN_ROOT%A+MATH_TOOLS 6   �  @   a   COMPUTE_HERMITIAN_ROOT%POW+MATH_TOOLS "   �  ^       LM2IND+COMM_UTILS $   J  @   a   LM2IND%L+COMM_UTILS $   �  @   a   LM2IND%M+COMM_UTILS $   �  k       INITIALIZE_MCMC_MOD .   5  P   a   INITIALIZE_MCMC_MOD%PARAMFILE 3   �  @   a   INITIALIZE_MCMC_MOD%COMM_MASTER_IN !   �  H       CLEANUP_MCMC_MOD ,      g       SAMPLE_CLS_AND_ALMS_BY_MCMC 7   t   X   a   SAMPLE_CLS_AND_ALMS_BY_MCMC%RNG_HANDLE /   �   �   a   SAMPLE_CLS_AND_ALMS_BY_MCMC%CL .   x!  T   a   SAMPLE_CLS_AND_ALMS_BY_MCMC%S "   �!  �       LNL_JOINT_ALMS_CL %   t"  @   a   LNL_JOINT_ALMS_CL%CL    �"  x       RESCALE_ALMS "   ,#  @   a   RESCALE_ALMS%LMIN "   l#  @   a   RESCALE_ALMS%LMAX "   �#  @   a   RESCALE_ALMS%SPEC     �#  @   a   RESCALE_ALMS%CL "   ,$  �   a   RESCALE_ALMS%ALMS 